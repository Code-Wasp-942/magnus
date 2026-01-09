# back_end/python_scripts/tests/test_services/test_mma_mcp.py
import os
import random
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
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


async def execute_mathematica(
    code: str,
)-> str:
    
    server_address = os.getenv("MAGNUS_ADDRESS", "127.0.0.1:8017")
    token = os.getenv("MAGNUS_TOKEN")
    if not token:
        raise ValueError("❌ Environment variable 'MAGNUS_TOKEN' is not set.")
    url = f"http://{server_address}/api/services/mma-mcp/mcp?token={token}"
    
    transport = StreamableHttpTransport(url=url)
    
    async with Client(transport) as client:
        
        target_tool = "execute_mathematica"
        result = await client.call_tool(
            name = target_tool,
            arguments = {"code": code}
        )
        
        output = ""
        if hasattr(result, 'content'):
            for item in result.content:
                if hasattr(item, 'text'):
                    output += item.text # type: ignore
        
        return output


async def main():
    
    N = min(5, len(cases))
    sampled_cases = random.sample(cases, N)
    task_inputs = [(code, ) for code in sampled_cases]
    
    print(f"🚀 Starting {N} concurrent tasks...")

    results = await run_tasks_concurrently_async(
        task = execute_mathematica,
        task_indexers = list(range(N)),
        task_inputs = task_inputs,
    )
    
    print("\n" + "=" * 50)
    
    for idx, result in results.items():
        original_code = task_inputs[idx][0]
        
        if isinstance(result, Exception):
            print(f"Task {idx} (Input: {original_code}) Failed:\n❌ {result}")
        else:
            print(f"Task {idx} (Input: {original_code}):\n✅ {result.strip()}")
            
        print("-" * 50)


if __name__ == "__main__":
    
    asyncio.run(main())