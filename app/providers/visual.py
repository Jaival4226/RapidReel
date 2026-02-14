import requests
import time
import asyncio
import logging
import random
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger("Foundry.Visuals")

class VisualProvider:
    """
    Handles AI Video Generation (Leonardo)
    """
    def __init__(self):
        self.base_url = "https://cloud.leonardo.ai/api/rest/v1"
        self.headers = {
            "Authorization": f"Bearer {settings.LEONARDO_API_KEY}",
            "Content-Type": "application/json"
        }

    async def refine(self, prompt: str, style: str) -> str:
        return f"{style} style, cinematic: {prompt}"

    async def generate_video(self, prompt: str, output_path: Path) -> bool:
        if settings.USE_MOCK_VEO:
            return await self._mock_generate(output_path)

        try:
            # 1. Generate Image
            image_id = await self._generate_image(prompt)
            if not image_id: return False

            # 2. Animate (Motion SVD)
            video_url = await self._generate_motion(image_id)
            if not video_url: return False

            # 3. Download
            return self._download_file(video_url, str(output_path))
        except Exception as e:
            logger.error(f"❌ Leonardo Error: {e}")
            return False

    async def _generate_image(self, prompt: str) -> str:
        url = f"{self.base_url}/generations"
        payload = {
            "prompt": prompt,
            "modelId": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3",
            "width": 1024, "height": 576, "num_images": 1
        }
        try:
            resp = requests.post(url, headers=self.headers, json=payload)
            if resp.status_code != 200: return None
            gen_id = resp.json()['sdGenerationJob']['generationId']
            
            for _ in range(30):
                await asyncio.sleep(2)
                data = requests.get(f"{self.base_url}/generations/{gen_id}", headers=self.headers).json()
                status = data['generations_by_pk']['status']
                if status == "COMPLETE":
                    return data['generations_by_pk']['generated_images'][0]['id']
                elif status == "FAILED": return None
            return None
        except: return None

    async def _generate_motion(self, image_id: str) -> str:
        url = f"{self.base_url}/generations/motion-svd"
        payload = {"imageId": image_id, "motionStrength": 5}
        try:
            resp = requests.post(url, headers=self.headers, json=payload)
            if resp.status_code != 200: return None
            gen_id = resp.json()['sdGenerationJob']['generationId']
            
            for _ in range(60):
                await asyncio.sleep(2)
                data = requests.get(f"{self.base_url}/generations/{gen_id}", headers=self.headers).json()
                status = data['generations_by_pk']['status']
                if status == "COMPLETE":
                    return data['generations_by_pk']['generated_images'][0]['motionMP4URL']
                elif status == "FAILED": return None
            return None
        except: return None

    def _download_file(self, url: str, local_filename: str) -> bool:
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
        except: return False

    async def _mock_generate(self, output_path: Path):
        await asyncio.sleep(2)
        with open(output_path, "wb") as f: f.write(b"mock")
        return True


class StockProvider:
    """
    Handles Stock Footage (Pexels)
    """
    def __init__(self):
        self.base_url = "https://api.pexels.com/videos"
        self.headers = {"Authorization": settings.PEXELS_API_KEY}

    async def search_and_download(self, query: str, output_path: Path) -> bool:
        return await asyncio.to_thread(self._search_sync, query, output_path)

    def _search_sync(self, query: str, output_path: Path) -> bool:
        logger.info(f"🔍 Pexels: Searching for '{query}'")
        url = f"{self.base_url}/search"
        params = {"query": query, "per_page": 1, "orientation": "landscape", "size": "medium"}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code != 200: return False
            
            data = response.json()
            if not data.get("videos"): return False

            # Find best MP4 link
            video_files = data["videos"][0]["video_files"]
            download_url = next((vf["link"] for vf in video_files if ".mp4" in vf["link"] and vf["width"] >= 1280), None)
            
            if not download_url:
                # Fallback to any MP4
                download_url = next((vf["link"] for vf in video_files if ".mp4" in vf["link"]), None)

            if download_url:
                logger.info(f"⬇️ Downloading Pexels Video...")
                return self._download_file(download_url, str(output_path))
            return False
        except Exception as e:
            logger.error(f"Pexels Error: {e}")
            return False

    def _download_file(self, url: str, local_filename: str) -> bool:
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
        except: return False

visual_provider = VisualProvider()
stock_provider = StockProvider()