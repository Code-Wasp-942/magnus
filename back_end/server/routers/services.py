# back_end/server/routers/services.py
import httpx
import logging
import asyncio
import socket
from typing import Optional, Dict, Any
from datetime import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .. import database
from .. import models
from ..models import JobStatus, Service
from ..schemas import ServiceResponse, ServiceCreate, PagedServiceResponse
from .._service_manager import service_manager
from .._magnus_config import magnus_config
from .auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# 防止同一服务的并发创建冲突 (检查-执行 竞态保护)
_service_spawn_locks = defaultdict(asyncio.Lock)

# 流量控制信号量字典
_service_semaphores: Dict[str, asyncio.Semaphore] = {}


@router.post(
    "/services",
    response_model=ServiceResponse,
)
async def create_service(
    service_data: ServiceCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
) -> models.Service:
    """
    创建或更新 Service (Upsert)。
    """
    # 1. 检查 ID 是否冲突
    existing = db.query(Service).filter(Service.id == service_data.id).first()
    data = service_data.model_dump()

    if existing:
        # 权限检查
        if existing.owner_id != current_user.id:
            raise HTTPException(
                status_code=403, 
                detail="You cannot modify a service created by another user."
            )

        # 信号量重置逻辑：如果修改了最大并发数
        if service_data.max_concurrency != existing.max_concurrency:
            if existing.id in _service_semaphores:
                del _service_semaphores[existing.id]
                logger.info(f"Concurrency limit changed for {existing.id}, semaphore reset.")

        # Update existing
        for k, v in data.items():
            setattr(existing, k, v)

        existing.owner_id = current_user.id
        
        # [Magnus Update] 配置变更，刷新 updated_at
        existing.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(existing)
        return existing

    # 2. Create new
    new_service = Service(
        **data,
        owner_id=current_user.id,
        is_active=True,
        # 初始化两个时间
        last_activity_time=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_service)
    db.commit()
    db.refresh(new_service)
    return new_service


@router.delete("/services/{service_id}")
async def delete_service(
    service_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    删除服务。仅拥有者可操作。
    """
    svc = db.query(Service).filter(Service.id == service_id).first()

    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    if svc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this service")

    db.delete(svc)
    db.commit()

    if service_id in _service_semaphores:
        del _service_semaphores[service_id]

    return {"message": "Service deleted successfully"}


@router.get(
    "/services",
    response_model=PagedServiceResponse,
)
async def list_services(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    owner_id: Optional[str] = None,
    # [Magnus Update] 新增筛选：只看活跃
    active_only: bool = False,
    # [Magnus Update] 新增排序：activity (默认) | updated
    sort_by: str = Query("activity", regex="^(activity|updated)$"),
    db: Session = Depends(database.get_db)
) -> Dict[str, Any]:
    """
    获取服务列表（支持分页、搜索、筛选、排序）
    """
    query = db.query(models.Service)

    # 1. 搜索逻辑
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Service.name.ilike(search_pattern),
                models.Service.id.ilike(search_pattern),
                models.Service.description.ilike(search_pattern),
            )
        )

    # 2. 用户筛选
    if owner_id and owner_id != "all":
        query = query.filter(models.Service.owner_id == owner_id)

    # 3. 活跃状态筛选 [Magnus Update]
    if active_only:
        query = query.filter(models.Service.is_active == True)

    total = query.count()

    # 4. 排序逻辑 [Magnus Update]
    if sort_by == "updated":
        query = query.order_by(models.Service.updated_at.desc())
    else:
        # Default: activity
        query = query.order_by(models.Service.last_activity_time.desc())

    items = query.offset(skip).limit(limit).all()

    return {"total": total, "items": items}


@router.api_route(
    "/services/{service_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_service_request(
    service_id: str,
    path: str,
    request: Request,
    db: Session = Depends(database.get_db)
) -> StreamingResponse:
    # 1. 基础检查
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if not service.is_active:
        raise HTTPException(status_code=503, detail="Service is inactive")

    # [Magnus Update] Keep-Alive: 只更新活跃时间，不碰 updated_at
    service.last_activity_time = datetime.utcnow()
    db.commit()

    # 2. 获取或创建信号量
    if service.id not in _service_semaphores:
        _service_semaphores[service.id] = asyncio.Semaphore(service.max_concurrency)

    sem = _service_semaphores[service.id]

    # 3. SLA 控制
    start_time = datetime.utcnow()
    total_budget = service.request_timeout

    def get_remaining_time() -> float:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        return max(0.0, total_budget - elapsed)

    # 4. 流量控制
    try:
        await asyncio.wait_for(sem.acquire(), timeout=get_remaining_time())
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=429,
            detail=f"Service is busy (Max concurrency {service.max_concurrency} reached)."
        )

    try:
        # === 进入流量控制区 ===

        # 5. 检查与拉起 (Spawn Logic)
        if get_remaining_time() <= 0:
            raise HTTPException(status_code=504, detail="Timeout while waiting for concurrency slot")

        async with _service_spawn_locks[service_id]:
            db.refresh(service)
            current_job = service.current_job

            should_revive = False
            if not current_job:
                should_revive = True
            elif current_job.status in [JobStatus.FAILED, JobStatus.TERMINATED, JobStatus.SUCCESS]:
                should_revive = True

            if should_revive:
                try:
                    port = service_manager.allocate_port(db)

                    env_cmd = "\n".join([
                        f"export MAGNUS_PORT={port}",
                        service.entry_command,
                    ])

                    new_job = models.Job(
                        task_name=service.job_task_name,
                        description=service.job_description,
                        user_id=service.owner_id,
                        namespace=service.namespace,
                        repo_name=service.repo_name,
                        branch=service.branch,
                        commit_sha=service.commit_sha,
                        gpu_count=service.gpu_count,
                        gpu_type=service.gpu_type,
                        cpu_count=service.cpu_count,
                        memory_demand=service.memory_demand,
                        runner=service.runner,
                        entry_command=env_cmd,
                        status=JobStatus.PENDING,
                        job_type=service.job_type,
                    )

                    db.add(new_job)
                    db.flush()

                    service.current_job_id = new_job.id
                    service.assigned_port = port
                    db.commit()

                    current_job = new_job
                    logger.info(f"Service {service.id} revived with Job {new_job.id} on port {port}")

                except Exception as e:
                    logger.error(f"Failed to revive service {service.id}: {e}")
                    raise HTTPException(status_code=500, detail=f"Service spawn failed: {e}")

        # 6. 等待就绪 (Wait Logic)
        is_ready = False

        while get_remaining_time() > 0:
            db.refresh(current_job)

            if current_job.status in [JobStatus.FAILED, JobStatus.TERMINATED]:
                raise HTTPException(status_code=502, detail="Service job failed during startup")

            if current_job.status in [JobStatus.PENDING, JobStatus.PAUSED]:
                # [Magnus Update] 等待期间也刷新活跃时间，防止被 Service Manager 误杀
                service.last_activity_time = datetime.utcnow()
                db.commit()
                await asyncio.sleep(1)
                continue

            if current_job.status == JobStatus.RUNNING:
                if not service.assigned_port:
                    await asyncio.sleep(1)
                    continue

                try:
                    with socket.create_connection(("127.0.0.1", service.assigned_port), timeout=0.5):
                        is_ready = True
                        break
                except (ConnectionRefusedError, socket.timeout, OSError):
                    service.last_activity_time = datetime.utcnow()
                    db.commit()
                    await asyncio.sleep(1)
                    continue

            await asyncio.sleep(1)

        if not is_ready:
            raise HTTPException(status_code=504, detail="Service startup timed out")

        # 7. 转发请求 (Forward Logic)
        service_config = magnus_config.get("server", {}).get("services", {})
        
        proxy_timeout = httpx.Timeout(
            connect=service_config.get("proxy_connect_timeout", 2.0),
            read=service_config.get("proxy_read_timeout", 600.0),
            write=service_config.get("proxy_write_timeout", 30.0),
            pool=service_config.get("proxy_pool_timeout", 5.0),
        )

        client = httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{service.assigned_port}",
            timeout=proxy_timeout,
            follow_redirects=True,
        )

        try:
            body = await request.body()
            rp_req = client.build_request(
                request.method,
                f"/{path}",
                content=body,
                headers=request.headers.raw,
                params=request.query_params,
            )

            # [Magnus Update] 转发前再次刷新活跃时间
            service.last_activity_time = datetime.utcnow()
            db.commit()

            r = await client.send(rp_req, stream=True)

            return StreamingResponse(
                r.aiter_raw(),
                status_code=r.status_code,
                headers=r.headers,
                background=BackgroundTask(client.aclose),
            )

        except httpx.ConnectError:
            await client.aclose()
            raise HTTPException(status_code=502, detail="Service running but connection failed.")
        except Exception as e:
            await client.aclose()
            logger.error(f"Proxy error for {service.id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    finally:
        sem.release()