# back_end/python_scripts/tests/test_services/test_mma_mcp.py
import random
import asyncio
import magnus
from pywheels import run_tasks_concurrently_async

cases = [
    "2 + 2",
    "Integrate[x^2 * Sin[x], x]",
    "Simplify[Sin[x]^2 + Cos[x]^2]",
    "Solve[x^2 - 5x + 6 == 0, x]",
    "Prime[100]",
    "Det[{{1, 2}, {3, 4}}]",
    "N[Pi, 50]",
    "D[Exp[x] * Sin[x], x]",
]

async def execute_mathematica(code: str) -> str:
    """
    使用 Magnus SDK 调用 mma-mcp 服务。
    SDK 会自动处理认证、连接和错误抛出。
    """
    # 直接调用服务
    # 注意：这里假设服务端的入口函数接收 "code" 参数
    result = await magnus.call_service_async(
        service_id="mma-mcp",
        payload={"code": code},
        timeout=300.0  # Mathematica 计算可能较慢，保持原有的长超时
    )
    
    # 简单的结果格式化
    if isinstance(result, dict) and "text" in result:
        return str(result["text"])
    return str(result)

async def main():
    # 随机采样测试用例
    N = min(5, len(cases))
    sampled_cases = random.sample(cases, N)
    task_inputs = [(code, ) for code in sampled_cases]
    
    print(f"🚀 Starting {N} concurrent tasks via Magnus SDK...")

    # 并发执行
    results = await run_tasks_concurrently_async(
        task=execute_mathematica,
        task_indexers=list(range(N)),
        task_inputs=task_inputs,
    )
    
    print("\n" + "=" * 50)
    
    # 输出结果
    for idx, result in results.items():
        original_code = task_inputs[idx][0]
        
        if isinstance(result, Exception):
            # SDK 定义的 MagnusError 会在这里被捕获并打印
            print(f"Task {idx} (Input: {original_code}) Failed:\n❌ {result}")
        else:
            print(f"Task {idx} (Input: {original_code}):\n✅ {result.strip()}")
            
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())