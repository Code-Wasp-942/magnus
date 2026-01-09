# back_end/python_scripts/tests/test_services/test_z_image.py
import io
import os
import httpx
import random
import asyncio
from PIL import Image
from typing import Optional
from pywheels import run_tasks_concurrently_async
from pywheels.miscellaneous import get_time_stamp
from pywheels.file_tools import delete_file, guarantee_file_exist


TIME_STAMP = get_time_stamp(show_minute=True, show_second=True)
TEMP_FILENAME = f"pictures/tmp_{TIME_STAMP}.png"
DEFAULT_ADDRESS = "127.0.0.1:8017"
SERVICE_PATH = "/api/services/tongyi-mai-z-image-turbo/generate"


prompts = [
    "A futuristic cyberpunk city with neon lights, raining, reflection on the ground, high quality, 8k, masterpiece",
    "Majestic snow-capped mountains reflected in a crystal clear lake, photorealistic, morning golden hour light, 8k",
    "Modern minimalist business office workspace, sleek macbook on white desk, bokeh background, bright natural lighting, professional",
    "Dynamic action shot of a baseball player hitting a home run, stadium crowd cheering in background, cinematic lighting, motion blur",
    "A steampunk laboratory with brass gears and steam pipes, detailed machinery, warm vintage lighting, intricate details",
]


async def generate_image(
    prompt: str,
    timeout: float = 600.0,
    height: int = 1024,
    width: int = 1024,
    negative_prompt: str = "blurry, low quality, distortion",
    num_inference_steps: int = 20,
    guidance_scale: float = 0.0,
    seed: Optional[int] = None,
)-> bytes:
    
    server_address = os.getenv("MAGNUS_ADDRESS", DEFAULT_ADDRESS)
    url = f"http://{server_address}{SERVICE_PATH}"
    
    optional_params = {}
    if seed is not None: optional_params["seed"] = seed
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            url,
            json={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "height": height,
                "width": width,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                **optional_params,
            }
        )
        response.raise_for_status()
        return response.content


async def main():
    
    timeout = 600.0
    height = 1024
    width = 1024
    negative_prompt = "blurry, low quality, distortion"
    num_inference_steps = 4
    guidance_scale = 0.0
    random_generator = random.Random(TIME_STAMP)
    seed = random_generator.randint(0, 2**32 - 1)
    
    N = min(5, len(prompts))
    sampled_prompts = random_generator.sample(prompts, N)
    task_inputs = [
        (prompt, timeout, height, width, negative_prompt, 
         num_inference_steps, guidance_scale, seed) 
        for prompt in sampled_prompts
    ]
    
    print(f"🚀 Starting {N} concurrent image generation tasks...")
    
    results = await run_tasks_concurrently_async(
        task = generate_image,
        task_indexers = list(range(N)),
        task_inputs = task_inputs,
    )
    
    print("\n" + "=" * 50)
    
    for idx, image_bytes in results.items():
        if isinstance(image_bytes, Exception):
            print(f"Task {idx} Failed: {image_bytes}")
            continue
            
        try:
            image = Image.open(io.BytesIO(image_bytes))
            print(f"Task {idx} Generated: {image.size} | Mode: {image.mode}")
            
            guarantee_file_exist(TEMP_FILENAME)
            image.save(TEMP_FILENAME, format="PNG")
            
            print(f"👀 Previewing Task {idx} (Prompt: {task_inputs[idx][0]})")
            input(f"   Saved to {TEMP_FILENAME}. Press [Enter] for next image...")
            
        except Exception as error:
            print(f"   Error processing image {idx}: {error}")
        finally:
            delete_file(TEMP_FILENAME)
    
    print("-" * 50)
    print("✨ All tasks completed.")


if __name__ == "__main__":
    
    asyncio.run(main())