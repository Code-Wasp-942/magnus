from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import models
from .._shared_file_manager import shared_file_manager, SharedFileRateLimitError, SharedFileValidationError
from .auth import get_current_user


router = APIRouter()


class SharedFileCreateRequest(BaseModel):
    expire_days: int = Field(..., ge=7, le=90)
    expected_size_gb: int = Field(..., ge=1, le=800)


class SharedFileCreateResponse(BaseModel):
    token: str
    expire_at: str
    expected_size_gb: int


@router.post("/shared-files", response_model=SharedFileCreateResponse)
def create_shared_file(
    payload: SharedFileCreateRequest,
    current_user: models.User = Depends(get_current_user),
):
    try:
        created = shared_file_manager.create_shared_folder(current_user.id, payload.expire_days, payload.expected_size_gb)
    except SharedFileRateLimitError as error:
        raise HTTPException(status_code=429, detail=str(error))
    except SharedFileValidationError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {
        "token": created["token"],
        "expire_at": created["expire_at"],
        "expected_size_gb": created["expected_size_gb"],
    }
