# back_end/python_scripts/magnus_debug.py
import os
import sys
import time
import signal
import datetime
from math import isinf

# === Configuration ===
HEARTBEAT_INTERVAL = 300  # 5 Minutes
BLUE = '\033[0;34m'
GREEN = '\033[0;32m'
YELLOW = '\033[0;33m'
RED = '\033[0;31m'
NC = '\033[0m'
PREFIX = f"{BLUE}[Magnus Debug]{NC}"

def handle_exit(signum, frame):
    """Handle termination signals gracefully (e.g. scancel)"""
    print(f"\n{PREFIX} {YELLOW}Session terminated by signal ({signum}). Cleaning up...{NC}", flush=True)
    sys.exit(0)

def main():
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    # 1. Parse Arguments (Duration in minutes)
    duration_minutes = float('inf')
    if len(sys.argv) > 1:
        try:
            duration_minutes = float(sys.argv[1])
        except ValueError:
            print(f"{PREFIX} {RED}Invalid duration format. Using infinite mode.{NC}")

    # 2. Get Environment Info
    user = os.environ.get("USER", "unknown")
    job_id = os.environ.get("SLURM_JOB_ID", "N/A")
    node_name = os.environ.get("SLURMD_NODENAME", os.uname().nodename)
    
    # 3. Print Welcome Banner
    print("="*60, flush=True)
    print(f"{PREFIX} Debug Session Started", flush=True)
    print(f"{PREFIX} User:      {GREEN}{user}{NC}", flush=True)
    print(f"{PREFIX} Node:      {YELLOW}{node_name}{NC}", flush=True)
    print(f"{PREFIX} Job ID:    {YELLOW}{job_id}{NC}", flush=True)
    print(f"{PREFIX} Duration:  {'Infinite' if isinf(duration_minutes) else f'{duration_minutes} min'}", flush=True)
    print("-" * 60, flush=True)
    print(f"   To connect to this session, run the following command", flush=True)
    print(f"   on your local terminal (or the login node):", flush=True)
    print(f"", flush=True)
    if job_id != "N/A":
        # 针对你的 magnus-connect 脚本逻辑，直接给用户 JobID
        print(f"       {GREEN}sudo magnus-connect {job_id}{NC}", flush=True)
    else:
        print(f"       {GREEN}sudo magnus-connect{NC}", flush=True)
    print(f"", flush=True)
    print("="*60, flush=True)

    # 4. The Loop
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    print(f"{PREFIX} Main loop started. Waiting for connections...", flush=True)

    while True:
        current_time = time.time()
        
        # Check if time is up
        if current_time >= end_time:
            print(f"{PREFIX} Time limit reached. Exiting.", flush=True)
            break
            
        # Calculate uptime
        uptime = str(datetime.timedelta(seconds=int(current_time - start_time)))
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"[{timestamp}] Heartbeat: Active (Uptime: {uptime})", flush=True)
        
        # Sleep logic (handle finite duration vs interval)
        remaining = end_time - current_time
        sleep_time = min(HEARTBEAT_INTERVAL, remaining)
        
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()