# back_end/server/routers/auth.py
import secrets
import logging
import jwt
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .. import database
from .. import models
from ..schemas import UserInfo, LoginResponse, FeishuLoginRequest
from .._magnus_config import magnus_config
from .._jwt_signer import jwt_signer
from .._feishu_client import feishu_client


logger = logging.getLogger(__name__)
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/feishu/login")


def generate_trust_token()-> str:
    return f"sk-{secrets.token_urlsafe(24)}"


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db),
)-> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            magnus_config["server"]["jwt_signer"]["secret_key"],
            algorithms=[magnus_config["server"]["jwt_signer"]["algorithm"]],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user


@router.post(
    "/auth/feishu/login",
    response_model=LoginResponse,
)
async def feishu_login(
    req: FeishuLoginRequest,
    db: Session = Depends(database.get_db),
):
    try:
        feishu_user = await feishu_client.get_feishu_user(req.code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    open_id = feishu_user.get("open_id") or feishu_user.get("union_id")
    if not open_id:
        raise HTTPException(status_code=400, detail="Missing OpenID")

    db_user = db.query(models.User).filter(models.User.feishu_open_id == open_id).first()

    if not db_user:
        db_user = models.User(
            feishu_open_id=open_id,
            name=feishu_user.get("name", "Unknown"),
            avatar_url=feishu_user.get("avatar_url"),
            email=feishu_user.get("email"),
            token=generate_trust_token(),
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    else:
        db_user.name = feishu_user.get("name", db_user.name)
        db_user.avatar_url = feishu_user.get("avatar_url", db_user.avatar_url)
        if not db_user.token:
            db_user.token = generate_trust_token()
        db.commit()
        db.refresh(db_user)

    access_token = jwt_signer.create_access_token(payload={"sub": db_user.id})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": db_user,
    }


@router.post(
    "/auth/token/refresh",
    response_model=UserInfo,
)
async def refresh_trust_token(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    new_token = generate_trust_token()
    current_user.token = new_token

    db.commit()
    db.refresh(current_user)

    logger.info(f"User {current_user.id} ({current_user.name}) refreshed their trust token.")

    return current_user


@router.get(
    "/users",
    response_model=List[UserInfo],
)
async def get_users(
    db: Session = Depends(database.get_db),
):
    users = db.query(models.User).order_by(models.User.name).all()
    return users