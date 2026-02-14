import requests
import time
import asyncio
import logging
from pathlib import Path
from app.core.config import settings

# Setup Logger
logger = logging.getLogger("Foundry.Visuals")

class VisualProvider:
    """ AI Generation (Leonardo) """
    async def refine(self, prompt: str, style: str) -> str:
        return f"{style} style: {prompt}"

    async def generate_video(self, prompt: str, output_path: Path) -> bool:
        path_str = str(output_path)
        if settings.USE_MOCK_VEO:
            logger.info(f"🎭 MOCK MODE: Simulating generation for '{prompt}'...")
            await asyncio.sleep(2)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(b"mock_video_bytes")
            return True
        return await asyncio.to_thread(self._run_leonardo_sync, prompt, path_str)

    def _run_leonardo_sync(self, prompt: str, output_filename: str) -> bool:
        # [KEEP YOUR EXISTING LEONARDO CODE HERE]
        # For brevity, I am pointing to the existing logic you had.
        print(f"🚀 Sending prompt to Leonardo: {prompt}")
        return False # Placeholder: Ensure you keep your full _run_leonardo_sync method!

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

class StockProvider:
    """ Stock Footage (Pexels) """
    def __init__(self):
        self.base_url = "https://api.pexels.com/videos"
        self.headers = {"Authorization": settings.PEXELS_API_KEY}

    async def search_and_download(self, query: str, output_path: Path) -> bool:
        return await asyncio.to_thread(self._search_sync, query, output_path)

    def _search_sync(self, query: str, output_path: Path) -> bool:
        logger.info(f"🔍 Searching Pexels for: '{query}'")
        try:
            url = f"{self.base_url}/search"
            params = {"query": query, "per_page": 1, "orientation": "landscape", "size": "medium"}
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200: return False
            
            data = response.json()
            if not data.get("videos"): return False

            # Get best MP4 link
            video_files = data["videos"][0]["video_files"]
            download_url = next((vf["link"] for vf in video_files if ".mp4" in vf["link"]), None)
            
            if download_url:
                return self._download_file(download_url, str(output_path))
            return False
        except Exception as e:
            logger.error(f"Pexels Error: {e}")
            return False

    def _download_file(self, url: str, local_filename: str) -> bool:
        try:
            Path(local_filename).parent.mkdir(parents=True, exist_ok=True)
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
        except: return False

visual_provider = VisualProvider()
stock_provider = StockProvider()