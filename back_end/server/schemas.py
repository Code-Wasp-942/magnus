from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from .models import JobType, JobStatus # ✅ 从 models 导入枚举，保证定义统一

__all__ = [
    "JobSubmission",
    "JobResponse",
    "PagedJobResponse",
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
    
    # ✅ 新增：任务类型，前端下拉框选择
    job_type: JobType = JobType.B2

class JobResponse(JobSubmission):
    id: str
    user_id: str
    
    # ✅ 更新：使用 Enum 类型，自动验证和序列化
    status: JobStatus
    
    # ✅ 新增：返回 SLURM ID (可能为空) 和 开始时间
    slurm_job_id: Optional[str] = None
    start_time: Optional[datetime] = None
    
    created_at: datetime

    # Pydantic 会自动从数据库模型的 relationship 中读取 user 对象
    user: Optional[UserInfo] = None 

    class Config:
        from_attributes = True

class PagedJobResponse(BaseModel):
    total: int
    items: List[JobResponse]

class FeishuLoginRequest(BaseModel):
    code: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo