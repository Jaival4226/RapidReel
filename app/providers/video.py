import time
import asyncio
from pathlib import Path
from google import genai
from google.genai import types
from app.core.config import settings
from app.core.logging import setup_logging

logger = setup_logging("Foundry-Video")

class VideoProvider:
    def __init__(self):
        # Initialize only if not mocking (or needed for Gemini)
        try:
            self.client = genai.Client(
                vertexai=True,
                project=settings.PROJECT_ID,
                location=settings.LOCATION
            )
        except Exception:
            logger.warning("Could not init VertexAI Client. (Okay if running mocks)")

    def refine_prompt(self, raw_prompt: str, style: str) -> str:
        # We allow Gemini to run even in Mock Veo mode, unless API key is missing
        if not settings.GEMINI_API_KEY:
             return f"Refined ({style}): {raw_prompt}"
             
        try:
            sys_msg = f"Convert to detailed visual description for AI Video. Style: {style}. Under 40 words."
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL_ID,
                contents=f"{sys_msg}\nInput: {raw_prompt}"
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            return raw_prompt

    async def generate_video(self, prompt: str, output_path: Path) -> bool:
        if settings.USE_MOCK_VEO:
            logger.info(f"🚧 MOCK VEO: Simulating generation for '{prompt}'...")
            await asyncio.sleep(3) 
            # Create a valid (but empty) file placeholder
            with open(output_path, "wb") as f:
                f.write(b"mock_video_bytes") 
            return True

        try:
            logger.info("🎥 Sending request to Veo...")
            operation = self.client.models.generate_videos(
                model=settings.VEO_MODEL_ID,
                prompt=prompt,
                config=types.GenerateVideosConfig(number_of_videos=1)
            )
            
            # Polling
            while not operation.done:
                logger.info("...rendering video...")
                await asyncio.sleep(10)
                operation = self.client.operations.get(operation)

            if operation.result.generated_videos:
                video_bytes = operation.result.generated_videos[0].video.video_bytes
                with open(output_path, "wb") as f:
                    f.write(video_bytes)
                return True
            return False

        except Exception as e:
            logger.error(f"Veo Error: {e}")
            return False

video_service = VideoProvider()