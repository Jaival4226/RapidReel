import requests
import time
import asyncio
import logging
import random
from pathlib import Path
from app.core.config import settings

# Setup Logger
logger = logging.getLogger("Foundry.Visuals")

# ==========================================
# 1. LEONARDO AI PROVIDER (Your Specific Code)
# ==========================================
class VisualProvider:
    async def refine(self, prompt: str, style: str) -> str:
        """
        Returns the prompt combined with the style.
        """
        return f"{style} style: {prompt}"

    async def generate_video(self, prompt: str, output_path: Path) -> bool:
        """
        Generates a video using Leonardo.ai's API (Motion 2.0).
        Wraps the synchronous requests in asyncio.to_thread to prevent blocking.
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

        # 2. RUN LEONARDO GENERATION (Threaded)
        return await asyncio.to_thread(self._run_leonardo_sync, prompt, path_str)

    def _run_leonardo_sync(self, prompt: str, output_filename: str) -> bool:
        """
        The stable, production-ready video generation method.
        Uses Motion 2.0 which is native to Text-to-Video.
        """
        print(f"🚀 Sending prompt to Leonardo (Motion 2.0 Fast)...")
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {settings.LEONARDO_API_KEY}"
        }

        # ⚡️ USE THE DEDICATED VIDEO ENDPOINT (Best for Text-to-Video)
        url_generate = "https://cloud.leonardo.ai/api/rest/v1/generations-text-to-video"
        
        payload = {
            "prompt": prompt,
            "model": "MOTION2", # Native text-to-video model
            "isPublic": False,
            
            # ✅ STABLE RESOLUTION: 16:9 for Motion 2.0
            "width": 832,   
            "height": 480
        }

        try:
            # --- START JOB ---
            response = requests.post(url_generate, json=payload, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ Leonardo Error {response.status_code}: {response.text}")
                return False
                
            data = response.json()
            
            # ID check for the specific motion job key
            # Motion 2.0 usually returns 'motionVideoGenerationJob'
            generation_id = (
                data.get('motionVideoGenerationJob', {}).get('generationId') or
                data.get('generationId')
            )
            
            if not generation_id:
                 print(f"❌ Failed to get Generation ID. Response: {data}")
                 return False
                 
            print(f"⏳ Job started! ID: {generation_id}")

            # --- POLL FOR COMPLETION ---
            url_get = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
            
            # Motion 2.0 is fast (usually ~30-60 seconds)
            for i in range(40): 
                time.sleep(5) 
                check_response = requests.get(url_get, headers=headers)
                
                if check_response.status_code == 200:
                    data = check_response.json()
                    gen_data = data.get('generations_by_pk')
                    
                    if not gen_data: 
                        print(f"   ... Waiting for server data...")
                        continue
                    
                    status = gen_data.get('status')
                    
                    if status == "COMPLETE":
                        print("✅ Generation Complete!")
                        items = gen_data.get('generated_images', [])
                        
                        # Motion 2.0 video is usually in 'motionMP4URL'
                        video_url = items[0].get('motionMP4URL') or items[0].get('url') if items else None
                        
                        if video_url:
                            return self._download_file(video_url, output_filename)
                        
                        print("❌ Job Complete but URL missing.")
                        return False
                
                    elif status == "FAILED":
                        print("❌ Generation Failed on Leonardo's side.")
                        return False
                    
                    print(f"   ... Status: {status} (Wait {i+1}/40)")

            print("❌ Timed out waiting for Leonardo.")
            return False

        except Exception as e:
            print(f"❌ Exception in Leonardo Provider: {e}")
            return False
        
    def _download_file(self, url: str, local_filename: str) -> bool:
        try:
            # Ensure directory exists
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

# ==========================================
# 2. PEXELS PROVIDER (Added back for Gemini Fallback)
# ==========================================
class StockProvider:
    def __init__(self):
        self.api_key = settings.PEXELS_API_KEY
        self.headers = {"Authorization": self.api_key}

    async def search_and_download(self, query: str, output_path: Path) -> bool:
        """
        Searching Pexels for stock footage (Async wrapper around Sync code).
        """
        return await asyncio.to_thread(self._run_pexels_sync, query, str(output_path))

    def _run_pexels_sync(self, query: str, output_path: str) -> bool:
        if not self.api_key:
            print("❌ PEXELS_API_KEY missing.")
            return False

        try:
            print(f"🔍 Pexels: Searching for '{query}'...")
            url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation=landscape"
            
            response = requests.get(url, headers=self.headers)
            if response.status_code != 200:
                print(f"❌ Pexels Search Failed: {response.status_code}")
                return False
                
            data = response.json()
            if not data.get("videos"):
                print("⚠️ No videos found on Pexels.")
                return False

            # Pick a random video
            video_data = random.choice(data["videos"])
            
            # Find Best HD Link
            best_link = None
            files = video_data.get("video_files", [])
            files.sort(key=lambda x: x["width"], reverse=True) # Sort largest first
            
            for f in files:
                # Prefer 720p or 1080p
                if 1280 <= f["width"] <= 1920:
                    best_link = f["link"]
                    break
            
            if not best_link and files:
                best_link = files[0]["link"]

            # Download
            print(f"⬇️ Downloading Pexels Video...")
            with requests.get(best_link, stream=True) as r:
                r.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            print("✅ Pexels Video Saved.")
            return True

        except Exception as e:
            print(f"❌ Pexels Error: {e}")
            return False

# ==========================================
# 3. EXPORTS
# ==========================================
visual_provider = VisualProvider()
stock_provider = StockProvider()