# back_end/server/routers/services.py
import httpx
import logging
import asyncio
import traceback
import socket
from typing import Optional, Dict, Any
from datetime import datetime
from collections import defaultdict # <--- 新增

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .. import database
from .. import models
from ..models import JobStatus, Service
from ..schemas import ServiceResponse, ServiceCreate, PagedServiceResponse
from .._service_manager import service_manager
from .auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# <--- 新增：内存中的锁字典，防止同一服务的并发创建冲突
# key: service_id, value: asyncio.Lock
_service_spawn_locks = defaultdict(asyncio.Lock)


@router.post(
    "/services",
    response_model=ServiceResponse,
)
async def create_or_update_service(
    service_data: ServiceCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
) -> models.Service:
    # ... (保持原样) ...
    existing = db.query(Service).filter(Service.id == service_data.id).first()
    data = service_data.model_dump()

    if existing:
        if existing.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this service")

        for k, v in data.items():
            setattr(existing, k, v)

        existing.owner_id = current_user.id

        db.commit()
        db.refresh(existing)
        return existing

    else:
        new_service = Service(
            **data,
            owner_id=current_user.id,
            is_active=True,
            last_activity_time=datetime.utcnow(),
        )
        db.add(new_service)
        db.commit()
        db.refresh(new_service)
        return new_service


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
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if not service.is_active:
        raise HTTPException(status_code=503, detail="Service is inactive")

    # Keep-Alive
    service.last_activity_time = datetime.utcnow()
    db.commit()

    # <--- 修改开始：进入临界区前，先定义锁
    # 使用 Service ID 级别的锁，不同服务的请求互不干扰
    async with _service_spawn_locks[service_id]:
        
        # [重要] 拿到锁后，必须刷新 service 对象
        # 因为在等待锁的过程中，前一个请求可能已经修改了数据库
        db.refresh(service)
        current_job = service.current_job

        # 决策与拉起 (Revive)
        should_revive = False
        if not current_job:
            should_revive = True
        elif current_job.status in [JobStatus.FAILED, JobStatus.TERMINATED, JobStatus.SUCCESS]:
            should_revive = True

        if should_revive:
            try:
                # 只有持有锁的这一个请求会执行到这里
                port = service_manager.allocate_port(db)

                # 注入环境变量
                env_cmd = "\n".join([
                    f"export MAGNUS_PORT={port}",
                    service.entry_command,
                ])

                new_job = models.Job(
                    task_name = service.name,
                    description = service.id,
                    user_id = service.owner_id,
                    namespace = service.namespace,
                    repo_name = service.repo_name,
                    branch = service.branch,
                    commit_sha = service.commit_sha,
                    gpu_count = service.gpu_count,
                    gpu_type = service.gpu_type,
                    cpu_count = service.cpu_count,
                    memory_demand = service.memory_demand,
                    runner = service.runner,
                    entry_command = env_cmd,
                    status = JobStatus.PENDING,
                    job_type = service.job_type,
                )

                db.add(new_job)
                db.flush()

                service.current_job_id = new_job.id
                service.assigned_port = port
                db.commit()
                
                # 更新本地变量，供后续逻辑使用
                current_job = new_job 
                logger.info(f"Service {service.id} revived with Job {new_job.id} on port {port}")

            except Exception as e:
                logger.error(f"Failed to revive service {service.id}: {e}")
                raise HTTPException(status_code=500, detail=f"Service spawn failed: {e}")
    # <--- 修改结束：锁释放，后续的 1023 个请求进来后，db.refresh 会发现 current_job 已经有了，直接跳过 if should_revive

    # 阻塞等待 (Blocking Wait)
    start_wait = datetime.utcnow()
    timeout_sec = service.request_timeout
    is_ready = False

    while (datetime.utcnow() - start_wait).total_seconds() < timeout_sec:
        # 注意：这里需要重新 refresh current_job，因为 Job 的状态是异步变化的
        db.refresh(current_job)

        # Fast Fail: 任务挂了
        if current_job.status in [JobStatus.FAILED, JobStatus.TERMINATED]:
            raise HTTPException(status_code=502, detail="Service job failed during startup")

        # Case 1: 还在排队或拉起中
        if current_job.status in [JobStatus.PENDING, JobStatus.PAUSED]:
            service.last_activity_time = datetime.utcnow()
            db.commit()
            await asyncio.sleep(1)
            continue

        # Case 2: 任务 Running，检查端口是否通
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
        if current_job.status == JobStatus.RUNNING:
             raise HTTPException(status_code=504, detail="Service process started but application init timed out")
        else:
             raise HTTPException(status_code=504, detail={"detail": "Service is queuing...", "job_id": current_job.id})

    # 转发 (Forward)
    target_url = f"http://127.0.0.1:{service.assigned_port}/{path}"
    if request.query_params:
        target_url += f"?{request.query_params}"

    try:
        client = httpx.AsyncClient(base_url=f"http://127.0.0.1:{service.assigned_port}")

        body = await request.body()

        rp_req = client.build_request(
            request.method,
            f"/{path}",
            content=body,
            headers=request.headers.raw,
            params=request.query_params,
            timeout=timeout_sec,
        )

        service.last_activity_time = datetime.utcnow()
        db.commit()

        r = await client.send(rp_req, stream=True)

        return StreamingResponse(
            r.aiter_raw(),
            status_code=r.status_code,
            headers=r.headers,
            background=None,
        )

    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Service process is running but connection failed.")
    except Exception as e:
        logger.error(f"Proxy error for {service.id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/services",
    response_model=PagedServiceResponse,
)
async def list_services(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    owner_id: Optional[str] = None,
    db: Session = Depends(database.get_db)
) -> Dict[str, Any]:
    # ... (保持原样) ...
    query = db.query(models.Service)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Service.name.ilike(search_pattern),
                models.Service.id.ilike(search_pattern),
                models.Service.description.ilike(search_pattern),
            )
        )

    if owner_id and owner_id != "all":
        query = query.filter(models.Service.owner_id == owner_id)

    total = query.count()

    items = query.order_by(models.Service.last_activity_time.desc()) \
                 .offset(skip) \
                 .limit(limit) \
                 .all()

    return {"total": total, "items": items}