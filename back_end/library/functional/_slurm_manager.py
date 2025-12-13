# back_end/library/functional/_slurm_manager.py
import time
import shutil
import logging
import traceback
import subprocess
from typing import Optional


__all__ = [
    "SlurmManager",
    "SlurmError",
    "SlurmResourceError",
]


logger = logging.getLogger(__name__)


class SlurmError(Exception):
    pass


class SlurmResourceError(SlurmError):
    pass


class SlurmManager:

    def __init__(
        self
    )-> None:
        
        # 严格环境检查
        required_commands = ["sbatch", "squeue", "scancel", "sinfo"]
        missing_commands = [command for command in required_commands if shutil.which(command) is None]
        if missing_commands:
            error_msg = (
                f"CRITICAL: SLURM commands not found: {', '.join(missing_commands)}. "
                "Magnus requires a valid SLURM environment to operate."
            )
            logger.critical(error_msg)
            raise RuntimeError(error_msg)

    
    def get_cluster_free_gpus(
        self,
    )-> int:
        
        """
        获取集群空闲 GPU 总数
        
        策略:
        1. 供给侧: 解析 scontrol show node 获取集群 GPU 总容量 (Configured)
        2. 需求侧: 解析 squeue 统计所有正在运行任务的 GPU 占用量 (Allocated)
        3. 结果 = 容量 - 占用
        """
        
        try:
            # --- 步骤 1: 获取总容量 (Configured) ---
            # 我们相信 Gres 定义，这是物理真理
            cmd_capacity = ["scontrol", "show", "node", "--future"]
            res_capacity = subprocess.run(cmd_capacity, capture_output=True, text=True, check=True)
            
            total_capacity = 0
            for line in res_capacity.stdout.split('\n'):
                line = line.strip()
                # 解析 Gres=gpu:rtx5090:2 或 Gres=gpu:2(S:0)
                if line.startswith("Gres=") and "gpu" in line:
                    try:
                        # 1. 拿到 "gpu:rtx5090:2" 或 "gpu:2(S:0)"
                        gres_part = line.split("Gres=")[1].split()[0]
                        # 2. 去掉可能的括号 "gpu:2"
                        gres_part = gres_part.split('(')[0]
                        # 3. 取最后一个冒号后的数字
                        count = int(gres_part.split(':')[-1])
                        total_capacity += count
                    except (ValueError, IndexError):
                        pass

            # --- 步骤 2: 获取当前占用 (Allocated) ---
            # 既然 AllocTRES 不靠谱，我们直接统计 RUNNING 状态的任务申请了多少资源
            # %D: 节点数, %b: 每个节点的 GRES (例如 gpu:rtx5090:1)
            cmd_usage = ["squeue", "--states=RUNNING", "--noheader", "--format=%D %b"]
            res_usage = subprocess.run(cmd_usage, capture_output=True, text=True, check=True)
            
            total_allocated = 0
            for line in res_usage.stdout.strip().split('\n'):
                if not line.strip(): continue
                
                parts = line.split(maxsplit=1)
                # 如果 parts 长度小于2，说明该任务没有申请 GRES (纯 CPU 任务)，跳过
                if len(parts) < 2: continue 
                
                num_nodes_str, gres_req = parts[0], parts[1]
                
                if "gpu" not in gres_req:
                    continue

                try:
                    num_nodes = int(num_nodes_str)
                    # 解析 gpu:rtx5090:1 或 gpu:1，处理可能出现的括号
                    gres_req = gres_req.split('(')[0]
                    gpu_per_node = int(gres_req.split(':')[-1])
                    
                    total_allocated += (num_nodes * gpu_per_node)
                except (ValueError, IndexError):
                    pass
            
            # --- 步骤 3: 计算空闲 ---
            total_free = max(0, total_capacity - total_allocated) 
            return total_free

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to query cluster status: {e.stderr}")
            return 0
        except Exception as e:
            logger.error(f"Error calculating free GPUs: {e}\n{traceback.format_exc()}")
            return 0
    
    
    def submit_job(
        self,
        entry_command: str, 
        gpus: int,
        job_name: str,
        gpu_type: Optional[str] = None,
        output_path: Optional[str] = None,
        slurm_latency: int = 1,
        overwrite_output: bool = True,
    ) -> str:
        
        """
        提交任务 (通过 Stdin 管道)
        
        策略:
        1. 构造完整的 Shell 脚本内容。
        2. 构造 sbatch 参数 (支持指定型号、自定义日志路径)。
        3. 通过 Stdin 管道传给 sbatch。
        4. 模拟 Immediate 模式：提交后等待检查，若 PENDING 则强制取消。
        """
        
        entry_command = f"sleep {slurm_latency + 1}" + "\n" + entry_command
        script_content = f"#!/bin/bash\n\n{entry_command}"
        
        command = [
            "sbatch",
            "--parsable",
            f"--job-name={job_name}",
        ]

        # 利用默认行为：不设置 error 则 stderr 合并到 output
        log_file = output_path if output_path else "magnus_%j.log"
        command.append(f"--output={log_file}")
        if not overwrite_output: command.append("--open-mode=append")
        
        # 处理 GPU 资源
        if gpus > 0:
            if gpu_type and gpu_type != "cpu":
                command.append(f"--gres=gpu:{gpu_type}:{gpus}")
            else:
                command.append(f"--gres=gpu:{gpus}")

        job_id = None
        try:
            gpu_info = f"{gpu_type}:{gpus}" if (gpu_type and gpus > 0) else f"{gpus}"
            logger.info(f"🚀 Submitting '{job_name}' via stdin (GPUs: {gpu_info})...")
            
            result = subprocess.run(
                command, 
                input=script_content,
                capture_output=True, 
                text=True, 
                check=True
            )
            
            job_id = result.stdout.strip()

            time.sleep(slurm_latency)
            
            status = self.check_job_status(job_id)
            
            if status == "PENDING":
                logger.warning(f"⚠️ Job {job_id} is PENDING (Resource unavailable). Triggering Immediate Kill...")
                self.kill_job(job_id) 
                raise SlurmResourceError("Resources unavailable immediately (Simulated)")
            
            elif status in ["FAILED", "UNKNOWN", "BOOT_FAIL", "NODE_FAIL"]:
                raise SlurmError(f"Job failed immediately after submission (Status: {status})")
            
            return job_id
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ sbatch execution failed: {e.stderr}")
            raise SlurmError(f"Submission failed: {e.stderr}")
        
        except SlurmResourceError:
            raise
        
        except Exception as e:
            logger.error(f"❌ Unexpected submission error: {e}")
            if job_id:
                logger.warning(f"🧹 Cleaning up job {job_id} due to unexpected error...")
                try:
                    self.kill_job(job_id)
                except:
                    pass
            raise SlurmError(f"Unexpected error: {e}")

    
    def check_job_status(
        self, 
        slurm_job_id: str,
    )-> str:
        
        """
        查询 slurm 任务状态
        返回: PENDING | RUNNING | COMPLETED | FAILED | UNKNOWN
        """
        
        command = ["squeue", "-h", "-j", slurm_job_id, "-o", "%t"]
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            state = result.stdout.strip()
            
            if not state:
                # squeue 查不到，说明任务已经不在队列中（结束了）
                # 这里默认它 COMPLETED，因为如果是 FAILED 通常会有记录
                return "COMPLETED"

            # 映射 SLURM 状态码
            # R=Running, PD=Pending, CG=Completing, CD=Completed, 
            # F=Failed, CA=Cancelled, TO=Timeout
            mapping = {
                "R": "RUNNING",
                "PD": "PENDING",
                "CG": "RUNNING",
                "CD": "COMPLETED",
                "F": "FAILED",
                "CA": "FAILED",
                "TO": "FAILED",
            }
            return mapping.get(state, "UNKNOWN")
        
        except Exception as e:
            logger.error(f"Failed to check job status {slurm_job_id}: {e}")
            return "UNKNOWN"

    
    def kill_job(
        self, 
        slurm_job_id: str
    )-> None:
        
        """
        终止任务 (scancel)
        """
        
        command = [
            "scancel",
            "--signal=KILL",
            slurm_job_id,
        ]
        
        try:
            subprocess.run(command, check=False)
        except Exception as error:
            logger.error(f"scancel failed for job {slurm_job_id}: {error}")