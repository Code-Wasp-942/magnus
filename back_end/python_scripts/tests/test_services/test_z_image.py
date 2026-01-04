# back_end/python_scripts/tests/test_services/test_z_image.py
import asyncio
import os
import io
import httpx
from PIL import Image
from pywheels import run_tasks_concurrently_async
from pywheels.miscellaneous import get_time_stamp

# Configuration
TEMP_FILENAME = f"pictures/tmp_{get_time_stamp(show_minute=True, show_second=True)}.png"
DEFAULT_ADDRESS = "127.0.0.1:8017"
SERVICE_PATH = "/api/services/tongyi-mai-z-image-turbo/generate"

async def main():
    
    N = 1 
    
    async def _generate_and_preview(prompt: str) -> str:
        server_address = os.getenv("MAGNUS_ADDRESS", DEFAULT_ADDRESS)
        url = f"http://{server_address}{SERVICE_PATH}"
        
        print(f"Post request to: {url}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    url,
                    json={
                        "prompt": prompt,
                        "negative_prompt": "blurry, low quality, distortion",
                        "width": 1024,
                        "height": 1024,
                        "num_inference_steps": 20
                    }
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                return f"HTTP Error: {e.response.status_code} - {e.response.text}"
            except httpx.RequestError as e:
                return f"Connection Error: {str(e)}"
            
            try:
                image_bytes = response.content
                image = Image.open(io.BytesIO(image_bytes))
                
                print(f"✅ Generated: {image.size} | Mode: {image.mode}")
                image.save(TEMP_FILENAME, format="PNG")
                
                return f"Image saved to {TEMP_FILENAME}"

            except Exception as e:
                return f"Processing Error: {str(e)}"

    results = await run_tasks_concurrently_async(
        task = _generate_and_preview,
        task_indexers = list(range(N)),
        task_inputs = [(
            "A futuristic cyberpunk city with neon lights, raining, reflection on the ground, high quality, 8k, masterpiece",
        )] * N,
    )
    
    print("\n" + "=" * 50)
    for idx, result in results.items():
        print(f"Task {idx}: {result}")
    print("-" * 50)

    if os.path.exists(TEMP_FILENAME):
        try:
            print(f"\n👀 Previewing {TEMP_FILENAME}...")
            input("Press [Enter] to cleanup and exit...")
        finally:
            os.remove(TEMP_FILENAME)
            print("🗑️  Temporary file removed.")

if __name__ == "__main__":
    asyncio.run(main())