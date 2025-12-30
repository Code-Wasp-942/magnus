# back_end/server/routers/services.py
import httpx
import logging
import asyncio
import traceback
from typing import Optional, Dict, Any
from datetime import datetime

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


@router.post(
    "/services",
    response_model=ServiceResponse,
)
async def create_or_update_service(
    service_data: ServiceCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
)-> models.Service:
    existing = db.query(Service).filter(Service.id == service_data.id).first()
    data = service_data.model_dump()

    if existing:
        if existing.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this service")

        for k, v in data.items():
            setattr(existing, k, v)

        # 确保 owner 不被覆盖
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
)-> StreamingResponse:
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if not service.is_active:
        raise HTTPException(status_code=503, detail="Service is inactive")

    # Keep-Alive
    service.last_activity_time = datetime.utcnow()
    db.commit()

    current_job = service.current_job

    # 决策与拉起 (Revive)
    should_revive = False
    if not current_job:
        should_revive = True
    elif current_job.status in [JobStatus.FAILED, JobStatus.TERMINATED, JobStatus.SUCCESS]:
        should_revive = True

    if should_revive:
        try:
            port = service_manager.allocate_port(db)

            # 注入环境变量
            env_cmd = "\n".join([
                f"export MAGNUS_PORT={port}",
                service.entry_command,
            ])

            new_job = models.Job(
                task_name=service.name,
                description=service.id,
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

    # 阻塞等待 (Blocking Wait)
    start_wait = datetime.utcnow()
    timeout_sec = service.request_timeout

    while current_job.status in [JobStatus.PENDING, JobStatus.PAUSED]:
        if (datetime.utcnow() - start_wait).total_seconds() > timeout_sec:
            raise HTTPException(status_code=504, detail={"detail": "Service is queuing...", "job_id": current_job.id})

        service.last_activity_time = datetime.utcnow()
        db.commit()

        await asyncio.sleep(1)
        db.refresh(current_job)

        if current_job.status in [JobStatus.FAILED, JobStatus.TERMINATED]:
            raise HTTPException(status_code=502, detail="Service job failed during startup")

    # 转发 (Forward)
    if current_job.status != JobStatus.RUNNING:
        raise HTTPException(status_code=502, detail=f"Service unready (Status: {current_job.status})")

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
            timeout=10.0,
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
        raise HTTPException(status_code=502, detail="Service process is running but port is unreachable. Application might be initializing.")
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
)-> Dict[str, Any]:
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