import edge_tts
import httpx
import logging
import asyncio
import os
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger("Foundry.Audio")

class AudioProvider:
    async def generate(self, text: str, output_path: Path, force_premium: bool = False) -> bool:
        """
        Smart Audio Generation Strategy:
        1. Check Mock Mode.
        2. If Premium Requested -> Try ElevenLabs.
           -> If ElevenLabs fails (API error or No Key), FALLBACK to EdgeTTS.
        3. If Free Requested (or Fallback active) -> Run EdgeTTS.
        """
        # 1. Mock Mode
        if settings.USE_MOCK_AUDIO:
            logger.info("🚧 MOCK AUDIO: Generating dummy file.")
            with open(output_path, "wb") as f: f.write(b"mock_bytes")
            return True

        if not text or not text.strip():
            logger.warning("⚠️ Audio skipped: No text provided.")
            return False

        # 2. Premium Strategy (ElevenLabs)
        if force_premium:
            if settings.ELEVENLABS_API_KEY:
                logger.info("💎 Attempting ElevenLabs generation...")
                success = await self._elevenlabs(text, output_path)
                if success:
                    return True
                logger.warning("⚠️ ElevenLabs failed. Triggering Fail-Safe (EdgeTTS)...")
            else:
                logger.warning("⚠️ Premium requested but ELEVENLABS_API_KEY is missing in .env. Falling back to Free.")

        # 3. Standard/Fallback Strategy (EdgeTTS)
        return await self._edgetts(text, output_path)

    async def _edgetts(self, text: str, path: Path) -> bool:
        """Helper for Free Audio"""
        try:
            logger.info(f"🎤 EdgeTTS: Generating '{text[:15]}...'")
            communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
            await communicate.save(str(path))
            
            if path.exists() and path.stat().st_size > 0:
                logger.info(f"✅ EdgeTTS Success ({path.stat().st_size} bytes)")
                return True
            logger.error("❌ EdgeTTS file was created but is empty.")
            return False
        except Exception as e:
            logger.error(f"❌ EdgeTTS Critical Failure: {e}")
            return False

    async def _elevenlabs(self, text: str, path: Path) -> bool:
        """Helper for Paid Audio"""
        # Voice ID: 'Rachel' (American, Female, Calm)
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        headers = {
            "xi-api-key": settings.ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
                
                if resp.status_code == 200:
                    with open(path, "wb") as f: f.write(resp.content)
                    logger.info(f"✅ ElevenLabs Success ({len(resp.content)} bytes)")
                    return True
                elif resp.status_code == 401:
                    logger.error("❌ ElevenLabs Error: Invalid API Key (401). Check .env!")
                elif resp.status_code == 402:
                    logger.error("❌ ElevenLabs Error: Out of Credits (402).")
                else:
                    logger.error(f"❌ ElevenLabs API Error {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"❌ ElevenLabs Connection Error: {e}")
            return False

audio_provider = AudioProvider()