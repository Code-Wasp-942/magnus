import secrets
import enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from datetime import datetime
from .database import Base

def generate_hex_id() -> str:
    return secrets.token_hex(8)

# ✅ 新增：任务类型枚举
class JobType(str, enum.Enum):
    A1 = "A1"  # 最高优先级，不可抢占
    A2 = "A2"  # 高优先级，不可抢占
    B1 = "B1"  # 中优先级，可被 A 类抢占
    B2 = "B2"  # 低优先级，可被 A 类抢占

# ✅ 新增：任务状态枚举
class JobStatus(str, enum.Enum):
    PENDING = "Pending"   # 在 Magnus 队列中等待
    RUNNING = "Running"   # 在 SLURM 中执行
    PAUSED  = "Paused"    # 被抢占挂起 (B类专属)
    SUCCESS = "Success"
    FAILED  = "Failed"

class User(Base):
    __tablename__ = "users"

    # 我们自己的 User ID (16位 Hex)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_hex_id)
    
    # 飞书的唯一标识 (Open ID)
    feishu_open_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    
    # 基本信息
    name: Mapped[str] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 关联关系
    jobs: Mapped[list["Job"]] = relationship(back_populates="user")

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_hex_id)
    
    task_name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    user: Mapped["User"] = relationship(back_populates="jobs")
    
    namespace: Mapped[str] = mapped_column(String)
    repo_name: Mapped[str] = mapped_column(String)
    branch: Mapped[str] = mapped_column(String)
    commit_sha: Mapped[str] = mapped_column(String)
    
    gpu_count: Mapped[int] = mapped_column(Integer)
    gpu_type: Mapped[str] = mapped_column(String)
    
    entry_command: Mapped[str] = mapped_column(Text)
    
    # 👇 关键变更：
    # 1. status 改用 Enum 类型，更加严谨
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    
    # 2. 新增 job_type，默认为 B2 (最低优先级)
    job_type: Mapped[JobType] = mapped_column(SQLEnum(JobType), default=JobType.B2)
    
    # 3. SLURM Job ID (可能为空，因为Pending/Paused时没有ID)
    slurm_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 4. 实际运行开始时间
    # 每次从 Pending/Paused -> Running 时更新
    # 用于计算运行持续时间，实现 "杀最新启动的任务" (LIFO) 策略
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)