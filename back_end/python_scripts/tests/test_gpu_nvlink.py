# back_end/python_scripts/tests/test_gpu_nvlink.py
import torch
import time

def perform_bandwidth_test(src_device, dst_device, size_mb=1024):
    num_elements = (size_mb * 1024 * 1024) // 4
    x = torch.randn(num_elements, device=src_device, dtype=torch.float32)
    
    # Warmup
    for _ in range(5):
        _ = x.to(dst_device)
    torch.cuda.synchronize()

    start_time = time.time()
    iterations = 10
    
    for _ in range(iterations):
        _ = x.to(dst_device)
    
    torch.cuda.synchronize()
    end_time = time.time()

    total_bytes = size_mb * 1024 * 1024 * iterations
    duration = end_time - start_time
    bandwidth = (total_bytes / duration) / (1024**3) 

    return bandwidth

def main():
    print(f"🚀 [Magnus] GPU Interconnect Test")
    print(f"PyTorch Version: {torch.__version__}")
    
    if not torch.cuda.is_available():
        print("❌ Error: No CUDA environment detected.")
        return

    n_devices = torch.cuda.device_count()
    print(f"Detected GPUs: {n_devices}")
    
    if n_devices < 2:
        print("❌ Need at least 2 GPUs to test interconnect.")
        return

    for i in range(n_devices):
        print(f"GPU {i}: {torch.cuda.get_device_name(i)}")

    print("-" * 50)

    print("🔍 Phase 1: P2P Access Check (Software Capability)")
    p2p_0_to_1 = torch.cuda.can_device_access_peer(0, 1)
    p2p_1_to_0 = torch.cuda.can_device_access_peer(1, 0)

    print(f"GPU 0 -> GPU 1 P2P: {'✅ Enabled' if p2p_0_to_1 else '❌ Disabled (via CPU)'}")
    print(f"GPU 1 -> GPU 0 P2P: {'✅ Enabled' if p2p_1_to_0 else '❌ Disabled (via CPU)'}")
    
    if not p2p_0_to_1:
        print("\n⚠️ Warning: P2P disabled. Performance will be limited by CPU RAM bandwidth.")

    print("-" * 50)

    print("🏎️ Phase 2: Bandwidth Stress Test")
    print("Transferring 10GB payload between cards...")
    
    speed_0_1 = perform_bandwidth_test(torch.device("cuda:0"), torch.device("cuda:1"))
    print(f"Bandwidth (0 -> 1): {speed_0_1:.2f} GB/s")
    
    speed_1_0 = perform_bandwidth_test(torch.device("cuda:1"), torch.device("cuda:0"))
    print(f"Bandwidth (1 -> 0): {speed_1_0:.2f} GB/s")

    print("-" * 50)
    print("⚖️ [Magnus Verdict]")
    avg_speed = (speed_0_1 + speed_1_0) / 2
    
    if avg_speed > 150:
        print(f"💎 Ultra High Speed ({avg_speed:.1f} GB/s): Likely A100/H100 NVLink or NVSwitch.")
    elif avg_speed > 48:
        print(f"🥇 High Speed ({avg_speed:.1f} GB/s): Likely PCIe 5.0 x16 P2P or Consumer NVLink Bridge.")
    elif avg_speed > 24:
        print(f"🥈 Standard Speed ({avg_speed:.1f} GB/s): Likely PCIe 4.0 x16 P2P.")
    elif avg_speed > 11:
        print(f"🥉 Basic Speed ({avg_speed:.1f} GB/s): Likely PCIe 3.0 x16 P2P.")
    else:
        print(f"🐢 Low Speed ({avg_speed:.1f} GB/s): Likely System Memory Fallback (QPI/UPI bottleneck).")

if __name__ == "__main__":
    main()