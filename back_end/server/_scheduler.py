import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from pywheels.file_tools import guarantee_file_exist
from .database import SessionLocal
from .models import Job, JobStatus, JobType
from library.functional._slurm_manager import SlurmManager, SlurmResourceError
from ._magnus_config import magnus_config

__all__ = [
    "scheduler",
]

magnus_workspace_path = f"{magnus_config['server']['root']}/workspace"
guarantee_file_exist(magnus_workspace_path, is_directory=True)

logger = logging.getLogger(__name__)

class MagnusScheduler:
    
    def __init__(
        self,
    ):
        try:
            self.slurm_manager = SlurmManager()
            self.enabled = True
        except RuntimeError as e:
            logger.critical(f"Scheduler disabled due to missing SLURM: {e}")
            self.enabled = False

    def tick(
        self,
    ):
        if not self.enabled: return
        with SessionLocal() as db:
            try:
                self._sync_reality(db)
                self._make_decisions(db)
            except Exception as e:
                logger.error(f"Scheduler tick failed: {e}", exc_info=True)

    def _sync_reality(
        self, 
        db: Session,
    ):
        running_jobs = db.query(Job).filter(Job.status == JobStatus.RUNNING).all()
        for job in running_jobs:
            if not job.slurm_job_id:
                logger.warning(f"Job {job.id} is RUNNING but has no slurm_id. Marking FAILED.")
                job.status = JobStatus.FAILED
                continue

            real_status = self.slurm_manager.check_job_status(job.slurm_job_id)
            
            if real_status == "COMPLETED":
                marker_path = f"{magnus_workspace_path}/jobs/{job.id}/.magnus_success"
                if os.path.exists(marker_path):
                    logger.info(f"Job {job.id} completed successfully (Marker Verified).")
                    job.status = JobStatus.SUCCESS
                else:
                    logger.warning(f"Job {job.id} disappeared but NO success marker. Marking FAILED.")
                    job.status = JobStatus.FAILED
                job.slurm_job_id = None
            
            elif real_status in ["FAILED", "CANCELLED", "TIMEOUT"]:
                logger.warning(f"Job {job.id} failed in SLURM (Status: {real_status}).")
                job.status = JobStatus.FAILED
                job.slurm_job_id = None
            
            db.commit()

    def _make_decisions(
        self, 
        db: Session,
    ):
        real_free_gpus = self.slurm_manager.get_cluster_free_gpus()
        
        candidates = db.query(Job).filter(
            Job.status.in_([JobStatus.PENDING, JobStatus.PAUSED])
        ).all()
        if not candidates: return

        priority_map = {JobType.A1: 4, JobType.A2: 3, JobType.B1: 2, JobType.B2: 1}
        candidates.sort(
            key = lambda x: (priority_map[x.job_type], -x.created_at.timestamp()), 
            reverse = True,
        )

        for job in candidates:
            job_launched = False
            
            if real_free_gpus >= job.gpu_count:
                if self._start_job(db, job):
                    real_free_gpus -= job.gpu_count
                    job_launched = True
            
            elif job.job_type in [JobType.A1, JobType.A2]:
                needed = job.gpu_count - real_free_gpus
                potential_victims = db.query(Job).filter(
                    Job.status == JobStatus.RUNNING,
                    Job.job_type.in_([JobType.B1, JobType.B2])
                ).all()
                potential_victims.sort(key = lambda x: x.start_time.timestamp() if x.start_time else 0, reverse = True)
                
                victims = []
                recovered_gpus = 0
                for v in potential_victims:
                    if recovered_gpus >= needed: break
                    victims.append(v)
                    recovered_gpus += v.gpu_count
                
                if recovered_gpus >= needed:
                    logger.info(f"Preemption: Job {job.id} reclaiming {needed} GPUs.")
                    for v in victims: self._kill_and_pause(db, v)
                    real_free_gpus += recovered_gpus
                    if self._start_job(db, job):
                        real_free_gpus -= job.gpu_count
                        job_launched = True
            
            if not job_launched:
                logger.debug(f"Queue Blocked: Job {job.id} waiting. Stopping scheduling.")
                break

    def _start_job(
        self, 
        db: Session, 
        job: Job
    ) -> bool:
        job_working_table = f"{magnus_workspace_path}/jobs/{job.id}"
        guarantee_file_exist(f"{job_working_table}/slurm", is_directory=True)
        success_marker_path = f"{job_working_table}/.magnus_success"
        
        if os.path.exists(success_marker_path):
            try: os.remove(success_marker_path)
            except OSError: pass

        github_token = magnus_config["server"]["github_client"]["token"]
        auth_repo_url = f"https://oauth2:{github_token}@github.com/{job.namespace}/{job.repo_name}.git"

        conda_shell_path = magnus_config["server"]["scheduler"]["conda_shell_path"]
        execution_conda_environment = magnus_config["server"]["scheduler"]["execution_conda_environment"]
        
        # 构造 Wrapper 内容
        wrapper_content = f"""
import os
import sys
import traceback
import subprocess

def main():
    # --- 1. 配置注入 ---
    repo_url = {repr(auth_repo_url)}
    branch = {repr(job.branch)}
    commit_sha = {repr(job.commit_sha)}
    
    work_dir = {repr(job_working_table)}
    repo_dir = os.path.join(work_dir, "repository")
    marker_path = {repr(success_marker_path)}
    
    # 注入的 Conda 配置
    conda_sh = {repr(conda_shell_path)}
    execution_conda_environment = {repr(execution_conda_environment)}
    
    # --- 2. 准备代码环境 (Git) ---
    try:
        if not os.path.exists(repo_dir):
            subprocess.check_call(
                ["git", "clone", "--branch", branch, "--single-branch", repo_url, repo_dir],
                stdout=subprocess.DEVNULL,
                # stderr=subprocess.PIPE
            )
        
        subprocess.check_call(
            ["git", "checkout", commit_sha],
            cwd=repo_dir,
            stdout=subprocess.DEVNULL,
            # stderr=subprocess.PIPE
        )
         
    except subprocess.CalledProcessError as e:
        print("Magnus System Error: Git setup failed.", file=sys.stderr)
        if e.stderr: print(f"Git Error: {{e.stderr.decode().strip()}}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Magnus System Error: {{e}}", file=sys.stderr)
        sys.exit(1)

    # --- 3. 执行用户命令 (Conda Context Switch) ---
    try:
        os.chdir(repo_dir)
        user_cmd_str = {repr(job.entry_command)}
        
        # 核心逻辑：在一个 Bash Session 中完成 Source -> Activate -> Run
        # 只有这样，环境变量才能正确传递给 User Command
        full_command = f"source '{{conda_sh}}' && conda activate {{execution_conda_environment}} && {{user_cmd_str}}"
        
        # 使用 /bin/bash 显式执行，确保 source 命令可用
        ret_code = subprocess.call(
            full_command, 
            shell=True, 
            executable="/bin/bash"
        )
        
        if ret_code == 0:
            with open(marker_path, "w") as f: f.write("success")
            sys.exit(0)
        else:
            sys.exit(ret_code)
            
    except Exception as e:
        print(f"Magnus Execution Error: {{e}}\\nTraceback: \\n{{traceback.format_exc()}}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
        
        wrapper_path = f"{job_working_table}/wrapper.py"
        try:
            with open(wrapper_path, "w", encoding="utf-8") as f:
                f.write(wrapper_content)
        except IOError as e:
            logger.error(f"Failed to write wrapper: {e}")
            return False

        try:
            # 这里的 entry_command 只需要启动 python 即可
            # 具体的环境切换已经在 wrapper.py 内部完成了
            slurm_id = self.slurm_manager.submit_job(
                entry_command = f"python3 {wrapper_path}",
                gpus = job.gpu_count,
                job_name = job.task_name,
                gpu_type = job.gpu_type,
                output_path = f"{job_working_table}/slurm/output.txt",
                slurm_latency = magnus_config["server"]["scheduler"]["slurm_latency"],
                overwrite_output = False,
            )
            
            job.status = JobStatus.RUNNING
            job.slurm_job_id = slurm_id
            job.start_time = datetime.utcnow()
            db.commit()
            
            logger.info(f"Job {job.id} started (SLURM: {slurm_id})")
            return True
            
        except Exception as error:
            logger.error(f"Job {job.id} submission error: {error}")
            job.status = JobStatus.FAILED
            db.commit()
            return False

    def _kill_and_pause(self, db: Session, job: Job):
        if job.slurm_job_id:
            logger.info(f"Killing job {job.id}")
            self.slurm_manager.kill_job(job.slurm_job_id)
        job.status = JobStatus.PAUSED
        job.slurm_job_id = None
        job.start_time = None
        db.commit()

scheduler = MagnusScheduler()