import requests
import time
import asyncio
from pathlib import Path
from app.core.config import settings
import logging

# Setup Logger
logger = logging.getLogger("Foundry.Visual")

class VisualProvider:
    async def refine(self, prompt: str, style: str) -> str:
        return f"{style} style: {prompt}"

    async def generate_video(self, prompt: str, output_path: Path) -> bool:
        """
        Master function that routes the request to the correct provider
        based on your config settings.
        """
        path_str = str(output_path)
        
        # 1. MOCK MODE CHECK
        if settings.USE_MOCK_VEO:
            logger.info(f"🎭 MOCK MODE: Simulating generation for '{prompt}'...")
            await asyncio.sleep(2)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(b"mock_video_bytes_placeholder")
            return True

        # 2. ROUTING LOGIC
        if settings.VIDEO_PROVIDER == "kie":
            return await asyncio.to_thread(self._run_kie_sora_sync, prompt, path_str)
        elif settings.VIDEO_PROVIDER == "leonardo":
            return await asyncio.to_thread(self._run_leonardo_sync, prompt, path_str)
        else:
            logger.error(f"❌ Unknown Provider: {settings.VIDEO_PROVIDER}")
            return False

    # =================================================================
    # 🌟 ENGINE A: KIE.AI (Sora 2)
    # =================================================================
    def _run_kie_sora_sync(self, prompt: str, output_filename: str) -> bool:
        print(f"🚀 Sending prompt to Kie.ai (Sora 2 - 10s)...")
        
        headers = {
            "Authorization": f"Bearer {settings.KIE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        url_create = "https://api.kie.ai/api/v1/jobs/createTask"
        
        payload = {
            "model": "sora-2",  # 40 Credits / Video
            "input": {
                "prompt": prompt,
                "duration": 10,
                "aspect_ratio": "16:9"
            }
        }

        try:
            # 1. Start Job
            response = requests.post(url_create, json=payload, headers=headers)
            if response.status_code != 200:
                print(f"❌ Kie Error {response.status_code}: {response.text}")
                return False
                
            data = response.json()
            task_id = data.get("data", {}).get("id")
            
            if not task_id:
                 print(f"❌ Failed to get Task ID. Response: {data}")
                 return False
            print(f"⏳ Sora Job started! ID: {task_id}")

            # 2. Poll
            url_check = f"https://api.kie.ai/api/v1/jobs/getTask/{task_id}"
            for i in range(60): # Wait 5 minutes max
                time.sleep(5) 
                check = requests.get(url_check, headers=headers)
                
                if check.status_code == 200:
                    task_data = check.json().get("data", {})
                    status = task_data.get("status")
                    
                    if status == "SUCCEEDED":
                        print("✅ Sora Generation Complete!")
                        video_url = task_data.get("results", {}).get("url")
                        if video_url:
                            return self._download_file(video_url, output_filename)
                    
                    elif status == "FAILED":
                        print(f"❌ Kie Failed: {task_data.get('fail_reason')}")
                        return False
                    
                    print(f"   ... Status: {status} (Wait {i+1}/60)")
            
            return False

        except Exception as e:
            print(f"❌ Kie Exception: {e}")
            return False

    # =================================================================
    # 🎨 ENGINE B: LEONARDO (Motion 2.0) - [INTACT]
    # =================================================================
    def _run_leonardo_sync(self, prompt: str, output_filename: str) -> bool:
        print(f"🚀 Sending prompt to Leonardo (Motion 2.0)...")
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {settings.LEONARDO_API_KEY}"
        }
        url_generate = "https://cloud.leonardo.ai/api/rest/v1/generations-text-to-video"
        payload = {
            "prompt": prompt,
            "model": "MOTION2",
            "isPublic": False,
            "width": 832,
            "height": 480
        }

        try:
            response = requests.post(url_generate, json=payload, headers=headers)
            if response.status_code != 200:
                print(f"❌ Leonardo Error {response.status_code}: {response.text}")
                return False
            
            data = response.json()
            generation_id = (data.get('motionVideoGenerationJob', {}).get('generationId') or 
                             data.get('generationId'))
            
            if not generation_id: return False
            print(f"⏳ Job started! ID: {generation_id}")

            url_get = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
            for i in range(40): 
                time.sleep(5) 
                check = requests.get(url_get, headers=headers)
                if check.status_code == 200:
                    gen_data = check.json().get('generations_by_pk')
                    if gen_data and gen_data.get('status') == "COMPLETE":
                        items = gen_data.get('generated_images', [])
                        url = items[0].get('motionMP4URL') or items[0].get('url') if items else None
                        if url: return self._download_file(url, output_filename)
                    elif gen_data and gen_data.get('status') == "FAILED":
                        return False
                    print(f"   ... Status: {gen_data.get('status')} (Wait {i+1}/40)")
            return False
        except Exception as e:
            print(f"❌ Leonardo Exception: {e}")
            return False

    # =================================================================
    # 💾 UTILITIES
    # =================================================================
    def _download_file(self, url: str, local_filename: str) -> bool:
        try:
            Path(local_filename).parent.mkdir(parents=True, exist_ok=True)
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            print(f"💾 Saved to: {local_filename}")
            return True
        except Exception as e:
            print(f"❌ Failed to download: {e}")
            return False

# --- EXPORT INSTANCE ---
visual_provider = VisualProvider()