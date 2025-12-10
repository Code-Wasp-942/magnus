# back_end/server/schemas.py
from library import *


__all__ = [
    "JobSubmission",
    "JobResponse",
    "FeishuLoginRequest",
    "UserInfo",
    "LoginResponse",
]


class UserInfo(BaseModel):
    id: str
    name: str
    avatar_url: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True


class JobSubmission(BaseModel):
    task_name: str
    description: Optional[str] = None
    namespace: str = "PKU-Plasma"
    repo_name: str
    branch: str
    commit_sha: str
    entry_command: str
    gpu_type: str
    gpu_count: int = 1
    
    
class JobResponse(JobSubmission):
    id: str
    user_id: str
    status: str
    created_at: datetime

    # 2. ✅ 新增 user 字段，嵌套返回用户详细信息
    # Pydantic 会自动从数据库模型的 relationship 中读取 user 对象
    user: Optional[UserInfo] = None 

    class Config:
        from_attributes = True


class FeishuLoginRequest(BaseModel):
    code: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo