import os
import asyncio
import logging
import subprocess
from pathlib import Path
from app.core.config import settings
import whisper
import pysubs2
import edge_tts  # <--- New Library

logger = logging.getLogger("Foundry.Audio")

class AudioProvider:
    def __init__(self):
        self.model = None # Lazy load Whisper model

    async def generate(self, text: str, output_path: Path, is_paid: bool = False) -> bool:
        """
        Generates Audio using Microsoft Edge TTS (Free & High Quality).
        """
        try:
            # 1. Mock Mode Check
            if settings.USE_MOCK_AUDIO:
                logger.info("🎤 MOCK AUDIO: Generating silent placeholder...")
                return await self.generate_mock(output_path)

            logger.info(f"🎤 Generating EdgeTTS Audio: '{text[:30]}...'")
            
            # 2. Select Voice
            # Options: "en-US-AriaNeural" (Female), "en-US-ChristopherNeural" (Male), "en-US-GuyNeural" (Male)
            voice = "en-US-ChristopherNeural" 
            
            # 3. Generate
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
            
            logger.info(f"✅ Audio saved to: {output_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Audio Generation Failed: {e}")
            return False

    async def generate_mock(self, output_path: Path):
        """Generates 5 seconds of silence."""
        cmd = ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "5", "-y", str(output_path)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    def transcribe(self, audio_path: Path) -> Path:
        """
        Generates .srt subtitles using OpenAI Whisper.
        """
        try:
            if not audio_path.exists():
                logger.error(f"❌ Audio file missing: {audio_path}")
                return None

            # Lazy load Whisper to save RAM
            if not self.model:
                logger.info("📝 Loading Whisper Model (Base)...")
                self.model = whisper.load_model("base")

            logger.info(f"📝 Transcribing audio for subtitles...")
            result = self.model.transcribe(str(audio_path))
            
            # Convert Whisper JSON to Subtitles
            subs = pysubs2.SSAFile()
            for segment in result["segments"]:
                start_ms = int(segment["start"] * 1000)
                end_ms = int(segment["end"] * 1000)
                text = segment["text"].strip()
                
                # Add subtitle event
                subs.events.append(pysubs2.SSAEvent(start=start_ms, end=end_ms, text=text))

            srt_path = audio_path.with_suffix(".srt")
            subs.save(str(srt_path))
            
            logger.info(f"✅ Subtitles saved: {srt_path.name}")
            return srt_path

        except Exception as e:
            logger.error(f"❌ Transcription Failed: {e}")
            return None

audio_provider = AudioProvider()