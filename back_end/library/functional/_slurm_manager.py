import shutil
import subprocess
import logging
from typing import Optional

__all__ = [
    "SlurmManager",
    "SlurmError",
    "SlurmResourceError",
]

logger = logging.getLogger(__name__)

class SlurmError(Exception):
    """SLURM 通用错误"""
    pass

class SlurmResourceError(SlurmError):
    """资源不足错误 (对应 --immediate 失败)"""
    pass

class SlurmManager:
    """
    SLURM 集群管理器 (Wrapper) - Strict Mode
    
    职责：
    1. 提交任务 (sbatch)
    2. 查询资源 (sinfo)
    3. 管理任务状态 (squeue/scancel)
    
    注意：
    - 此类在初始化时会严格检查 SLURM 命令 (sbatch, squeue, scancel, sinfo)。
    - 如果环境不满足，直接抛出 RuntimeError。
    """
    
    def __init__(self) -> None:
        # 严格环境检查
        required_cmds = ["sbatch", "squeue", "scancel", "sinfo"]
        missing_cmds = [cmd for cmd in required_cmds if shutil.which(cmd) is None]
        
        if missing_cmds:
            error_msg = (
                f"CRITICAL: SLURM commands not found: {', '.join(missing_cmds)}. "
                "Magnus requires a valid SLURM environment to operate."
            )
            logger.critical(error_msg)
            raise RuntimeError(error_msg)

    def get_cluster_free_gpus(self) -> int:
        """
        获取集群当前空闲 GPU 总数
        """
        try:
            # 获取所有 idle 或 mixed 节点的 GPU 信息
            # sinfo -h -o "%G %t" -> "gpu:A100:8 idle"
            cmd = ["sinfo", "-h", "-o", "%G %t"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            total_free = 0
            for line in result.stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) < 2:
                    continue
                
                gres, state = parts[0], parts[1]
                
                # 简单粗暴的解析：如果是 idle，假设该节点所有 GPU 空闲
                # 这是一个简化策略，实际生产环境可能需要根据 Site Configuration 调整
                if "gpu" in gres and state == "idle":
                    try:
                        # 解析 "gpu:A100:8" 或 "gpu:8" 中的最后一个数字
                        count = int(gres.split(':')[-1]) 
                        total_free += count
                    except ValueError:
                        pass
                        
            return total_free
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute sinfo: {e.stderr}")
            return 0
        except Exception as e:
            logger.error(f"Error querying cluster resources: {e}")
            return 0

    def submit_job(self, entry_command: str, gpus: int) -> str:
        """
        提交任务 (手动模拟 Immediate 模式)
        
        策略变更：
        由于 sbatch 可能不支持 --immediate，改为：
        1. 正常提交任务。
        2. 等待 1 秒让 Slurm 调度。
        3. 检查状态。
        4. 如果是 PENDING (说明资源不够)，立即 scancel 并报错。
        5. 如果是 RUNNING，成功返回。
        """
        import time # 记得在文件头部导入 time

        # 构造 sbatch 命令 (去掉了 --immediate)
        cmd = [
            "sbatch",
            "--parsable",
            # "--immediate", # ❌ 移除这个不兼容的参数
            f"--gres=gpu:{gpus}", # 如果之后还需要指定型号，改这里，例如 f"--gres=gpu:rtx5090:{gpus}"
            "--output=magnus_%j.log",
            "--error=magnus_%j.err",
            "--job-name=magnus_job",
            "--wrap", entry_command
        ]

        job_id = None
        try:
            # 1. 提交
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            job_id = result.stdout.strip()
            
            # 2. 给 Slurm 调度器一点反应时间 (1秒通常足够)
            time.sleep(1) 
            
            # 3. 检查状态
            status = self.check_job_status(job_id)
            
            # 4. 判定
            if status == "PENDING":
                # 核心逻辑：如果是排队中，说明资源不足（或者是碎片化导致无法分配）
                # 我们必须撤回任务，保持 "Magnus 控制排队" 的原则
                logger.warning(f"Job {job_id} is PENDING in Slurm (simulated immediate failure). Cancelling...")
                self.kill_job(job_id)
                raise SlurmResourceError("Resources unavailable immediately (Simulated)")
                
            elif status == "FAILED" or status == "UNKNOWN":
                raise SlurmError(f"Job failed immediately after submission (Status: {status})")
                
            # 如果是 RUNNING 或 COMPLETED，说明成功抢到了资源
            return job_id
            
        except subprocess.CalledProcessError as e:
            logger.error(f"sbatch failed: {e.stderr}")
            raise SlurmError(f"Submission failed: {e.stderr}")
        except SlurmResourceError:
            raise # 直接抛出给上层处理
        except Exception as e:
            # 兜底：如果有 ID 且发生意外，尝试清理
            if job_id:
                self.kill_job(job_id)
            logger.error(f"Unexpected submission error: {e}")
            raise SlurmError(f"Unexpected error: {e}")

    def check_job_status(self, slurm_job_id: str) -> str:
        """
        查询任务状态
        返回: PENDING | RUNNING | COMPLETED | FAILED | UNKNOWN
        """
        # 使用 squeue 查询活跃任务状态
        cmd = ["squeue", "-h", "-j", slurm_job_id, "-o", "%t"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            state = result.stdout.strip()
            
            if not state:
                # squeue 查不到，说明任务已经不在队列中（结束了）
                # 这里默认它 COMPLETED，因为如果是 FAILED 通常会有记录
                # *注：更严谨的做法是去查 sacct，但在简单场景下这样足够
                return "COMPLETED"

            # 映射 SLURM 状态码
            # R=Running, PD=Pending, CG=Completing, CD=Completed, F=Failed, CA=Cancelled
            mapping = {
                "R": "RUNNING",
                "PD": "PENDING",
                "CG": "RUNNING",
                "CD": "COMPLETED",
                "F": "FAILED",
                "CA": "FAILED", 
                "TO": "FAILED" # Timeout
            }
            return mapping.get(state, "UNKNOWN")
            
        except Exception as e:
            logger.error(f"Failed to check job status {slurm_job_id}: {e}")
            return "UNKNOWN"

    def kill_job(self, slurm_job_id: str) -> None:
        """
        终止任务 (scancel)
        """
        try:
            subprocess.run(["scancel", slurm_job_id], check=False)
        except Exception as e:
            logger.error(f"scancel failed for job {slurm_job_id}: {e}")