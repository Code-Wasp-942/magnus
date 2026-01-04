# back_end/python_scripts/tests/test_services/test_mma_mcp.py
import asyncio
import os
import random
from typing import List, Tuple
from pywheels import run_tasks_concurrently_async
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def main():
    
    all_cases: List[Tuple[str]] = [
        ("2 + 2", ),
        ("Integrate[x^2 * Sin[x], x]", ),
        ("Simplify[Sin[x]^2 + Cos[x]^2]", ),
        ("Solve[x^2 - 5x + 6 == 0, x]", ),
        ("Prime[100]", ),
        ("Det[{{1, 2}, {3, 4}}]", ),
        ("N[Pi, 50]", ),
        ("D[Exp[x] * Sin[x], x]", ),
    ]
    
    task_inputs = random.sample(all_cases, min(5, len(all_cases)))
    N = len(task_inputs)
    
    print(f"🚀 Starting {N} concurrent tasks...")

    async def _call_mma_mcp(expression: str) -> str:
        
        server_address = os.getenv("MAGNUS_ADDRESS", "127.0.0.1:8017")
        url = f"http://{server_address}/api/services/mma-mcp/mcp"
        
        transport = StreamableHttpTransport(url=url)
        
        async with Client(transport) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            target_tool = "execute_mathematica"
            
            if target_tool in tool_names:
                result = await client.call_tool(
                    name = target_tool,
                    arguments = {"code": expression}
                )
                
                output = ""
                if hasattr(result, 'content'):
                    for item in result.content:
                        if hasattr(item, 'text'):
                            output += item.text # type: ignore
                            
                return f"Input:  {expression}\nOutput: {output}"
            else:
                return f"Error: Tool {target_tool} not found"

    results = await run_tasks_concurrently_async(
        task = _call_mma_mcp,
        task_indexers = list(range(N)),
        task_inputs = task_inputs,
    )
    
    print("\n" + "=" * 50)
    for result in results.values():
        print(result)
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())