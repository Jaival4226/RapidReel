import os
import requests
import random
import logging
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger("Foundry.StockProvider")

class StockProvider:
    def __init__(self):
        self.api_key = settings.PEXELS_API_KEY
        self.video_base_url = "https://api.pexels.com/videos"
        self.image_base_url = "https://api.pexels.com/v1"
        self.headers = {"Authorization": self.api_key}

    async def search_and_download(self, query: str, output_path: Path):
        """Searches for a VIDEO."""
        if not self.api_key:
            logger.warning("⚠️ Pexels Key missing.")
            self._create_mock(output_path)
            return

        logger.info(f"🔍 Pexels Video Search: '{query}'")
        try:
            params = {"query": query, "per_page": 5, "orientation": "landscape", "size": "medium"}
            response = requests.get(f"{self.video_base_url}/search", headers=self.headers, params=params, timeout=10)
            
            if response.status_code != 200:
                self._create_mock(output_path)
                return

            data = response.json()
            if not data.get("videos"):
                 self._create_mock(output_path)
                 return

            # Best Fit Logic
            video_files = random.choice(data["videos"]).get("video_files", [])
            best_video = next((v for v in video_files if v["height"] >= 720 and v["width"] > v["height"]), video_files[0] if video_files else None)

            if not best_video: raise Exception("No valid video files.")

            logger.info(f"⬇️ Downloading Pexels Video...")
            vid_res = requests.get(best_video["link"], stream=True, timeout=30)
            with open(output_path, "wb") as f:
                for chunk in vid_res.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info("✅ Pexels Video Saved.")

        except Exception as e:
            logger.error(f"❌ Pexels Video Failed: {e}")
            self._create_mock(output_path)

    # --- IMAGE (THUMBNAIL) ---
    async def search_and_download_image(self, query: str, output_path: Path):
        """Searches for a PHOTO."""
        if not self.api_key: return

        logger.info(f"🔍 Pexels Image Search: '{query}'")
        try:
            params = {"query": query, "per_page": 3, "orientation": "landscape"}
            response = requests.get(f"{self.image_base_url}/search", headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("photos"):
                    image_url = random.choice(data["photos"])["src"]["large2x"]
                    logger.info(f"⬇️ Downloading Thumbnail...")
                    img_res = requests.get(image_url, stream=True, timeout=20)
                    if img_res.status_code == 200:
                        with open(output_path, "wb") as f:
                            f.write(img_res.content)
                        logger.info("✅ Thumbnail Saved.")
        except Exception as e:
            logger.error(f"❌ Pexels Thumbnail Failed: {e}")

    def _create_mock(self, path: Path):
        with open(path, "wb") as f: f.write(b"Mock Content")

stock_provider = StockProvider()