import asyncio
import logging
from pathlib import Path
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger("Foundry.Visual")

class VisualProvider:
    def __init__(self):
        self.client = None
        if settings.GEMINI_API_KEY or not settings.USE_MOCK_VEO:
            try:
                self.client = genai.Client(vertexai=True, project=settings.PROJECT_ID, location=settings.LOCATION)
            except: pass

    async def refine(self, prompt: str, style: str) -> str:
        if not self.client: return prompt
        try:
            resp = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=f"Visual description for AI Video. Style: {style}. Under 40 words.\nInput: {prompt}"
            )
            return resp.text.strip()
        except: return prompt

    async def generate_video(self, prompt: str, path: Path) -> bool:
        if settings.USE_MOCK_VEO:
            logger.info("🚧 MOCK VEO: Simulating...")
            await asyncio.sleep(3)
            with open(path, "wb") as f: f.write(b"mock")
            return True

        try:
            op = self.client.models.generate_videos(
                model=settings.VEO_MODEL, prompt=prompt, config=types.GenerateVideosConfig(number_of_videos=1)
            )
            while not op.done:
                await asyncio.sleep(5)
                op = self.client.operations.get(op)
            
            if op.result.generated_videos:
                with open(path, "wb") as f: f.write(op.result.generated_videos[0].video.video_bytes)
                return True
        except Exception as e:
            logger.error(f"Veo Failed: {e}")
        return False

visual_provider = VisualProvider()