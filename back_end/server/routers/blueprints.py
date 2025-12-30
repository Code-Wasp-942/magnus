# back_end/server/routers/blueprints.py
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .. import database
from .. import models
from ..schemas import BlueprintResponse, BlueprintCreate, PagedBlueprintResponse, BlueprintParamSchema
from .._blueprint_manager import blueprint_manager
from .auth import get_current_user


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/blueprints",
    response_model=BlueprintResponse,
)
async def create_blueprint(
    bp: BlueprintCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1. 验证代码签名
    try:
        blueprint_manager.analyze_signature(bp.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. 检查 ID 是否冲突（如果是新建）
    # 注意：这里允许 overwrite (Update)，但如果是别人的蓝图则禁止覆盖
    existing = db.query(models.Blueprint).filter(models.Blueprint.id == bp.id).first()

    if existing:
        if existing.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You cannot modify a blueprint created by another user. Please verify the Blueprint ID.",
            )

        # Update existing
        existing.title = bp.title
        existing.description = bp.description
        existing.code = bp.code
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    # Create new
    db_bp = models.Blueprint(
        **bp.model_dump(),
        user_id=current_user.id,
    )
    db.add(db_bp)
    db.commit()
    db.refresh(db_bp)
    return db_bp


@router.delete("/blueprints/{blueprint_id}")
async def delete_blueprint(
    blueprint_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    删除蓝图。仅拥有者可操作。
    """
    bp = db.query(models.Blueprint).filter(models.Blueprint.id == blueprint_id).first()

    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    if bp.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this blueprint")

    db.delete(bp)
    db.commit()

    return {"message": "Blueprint deleted successfully"}


@router.get(
    "/blueprints",
    response_model=PagedBlueprintResponse,
)
async def list_blueprints(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    creator_id: Optional[str] = None,
    db: Session = Depends(database.get_db),
):
    """
    获取蓝图列表（支持分页、搜索、筛选）
    """
    query = db.query(models.Blueprint)

    # 1. 搜索逻辑 (Title, ID, Description)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Blueprint.title.ilike(search_pattern),
                models.Blueprint.id.ilike(search_pattern),
                models.Blueprint.description.ilike(search_pattern),
            )
        )

    # 2. 用户筛选
    if creator_id and creator_id != "all":
        query = query.filter(models.Blueprint.user_id == creator_id)

    total = query.count()

    # 3. 分页查询
    # 按更新时间倒序排列（最近更新的在前面）
    items = query.order_by(models.Blueprint.updated_at.desc())\
                 .offset(skip)\
                 .limit(limit)\
                 .all()

    return {"total": total, "items": items}


@router.get(
    "/blueprints/{blueprint_id}/schema",
    response_model=List[BlueprintParamSchema],
)
async def get_blueprint_schema(
    blueprint_id: str,
    db: Session = Depends(database.get_db),
):
    bp = db.query(models.Blueprint).filter(models.Blueprint.id == blueprint_id).first()
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    try:
        return blueprint_manager.analyze_signature(bp.code)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Invalid blueprint code: {e}")


@router.post("/blueprints/{blueprint_id}/run")
async def run_blueprint(
    blueprint_id: str,
    params: Dict[str, Any],
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    bp = db.query(models.Blueprint).filter(models.Blueprint.id == blueprint_id).first()
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    try:
        job_submission = blueprint_manager.execute(
            bp.code,
            params,
        )

        job_dict = job_submission.model_dump()

        db_job = models.Job(
            **job_dict,
            user_id=current_user.id,
            status=models.JobStatus.PENDING,
        )

        db.add(db_job)
        db.commit()
        db.refresh(db_job)

        logger.info(f"Blueprint {blueprint_id} launched job {db_job.id}")
        return {"message": "Blueprint launched", "job_id": db_job.id}

    except Exception as e:
        logger.error(f"Blueprint run failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))