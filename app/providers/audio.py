import edge_tts
import asyncio
import whisper
import logging
import os
from pathlib import Path

logger = logging.getLogger("Foundry.Audio")

class AudioProvider:
    def __init__(self):
        self.voice_free = "en-US-ChristopherNeural"
        self.model = None

    async def generate(self, text: str, output_path: Path, is_paid: bool = False) -> bool:
        """
        Generates audio using Edge TTS with Robust Retry Logic.
        """
        voice = self.voice_free
        
        # RETRY LOOP: Try 3 times
        for attempt in range(3):
            try:
                # Ensure directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Delete existing if present to ensure fresh write
                if output_path.exists():
                    os.remove(output_path)

                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(str(output_path))
                
                # Verify file
                if output_path.exists() and output_path.stat().st_size > 0:
                    logger.info(f"✅ Audio generated (Attempt {attempt+1})")
                    return True
            
            except Exception as e:
                logger.warning(f"⚠️ EdgeTTS Failed (Attempt {attempt+1}): {e}")
                await asyncio.sleep(2) # Wait 2s before retry
        
        logger.error("❌ Audio Generation Failed after 3 attempts.")
        return False

    def transcribe(self, audio_path: Path) -> Path:
        """
        Generates an SRT subtitle file from the audio.
        """
        if not self.model:
            logger.info("🧠 Loading Whisper Model...")
            self.model = whisper.load_model("tiny")

        try:
            logger.info(f"📝 Transcribing: {audio_path.name}")
            result = self.model.transcribe(str(audio_path))
            
            srt_path = audio_path.with_suffix(".srt")
            
            with open(srt_path, "w", encoding="utf-8") as f:
                for i, segment in enumerate(result["segments"]):
                    start = self._format_time(segment["start"])
                    end = self._format_time(segment["end"])
                    text = segment["text"].strip()
                    
                    f.write(f"{i+1}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")
            
            return srt_path

        except Exception as e:
            logger.error(f"❌ Transcription Failed: {e}")
            return None

    def _format_time(self, seconds: float) -> str:
        millis = int((seconds % 1) * 1000)
        seconds = int(seconds)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

audio_provider = AudioProvider()