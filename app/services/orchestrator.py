import asyncio
import subprocess
import logging
import os
import shutil
from sqlalchemy.orm import Session
from app.core.config import settings
from app.providers.audio import audio_provider
from app.providers.visual import visual_provider
from app.db.models import Task
from app.db.session import SessionLocal

logger = logging.getLogger("Foundry.Orchestrator")

class Orchestrator:
    async def process_task(self, task_id: str):
        """
        Runs the full pipeline:
        1. Refines the Visual Prompt for Veo.
        2. Uses the Monologue (or Prompt fallback) for Audio.
        3. Stitches them together.
        """
        db: Session = SessionLocal()
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            logger.error(f"Task {task_id} not found in DB.")
            return

        try:
            # --- 1. UPDATE STATUS ---
            logger.info(f"🚀 Starting Task {task_id}")
            task.status = "PROCESSING"
            db.commit()
            
            # Define Paths
            raw_vid = settings.TEMP_DIR / f"{task_id}_raw.mp4"
            audio = settings.TEMP_DIR / f"{task_id}.mp3"
            final = settings.OUTPUT_DIR / f"{task_id}_final.mp4" # <--- This is where the gallery looks

            # --- 2. PREPARE CONTENT ---
            # A. Refine Visuals
            refined_visual = await visual_provider.refine(task.prompt, task.style)
            logger.info(f"✨ Visual Refined: {refined_visual}")

            # B. Prepare Audio Script
            audio_script = task.monologue if task.monologue and task.monologue.strip() else task.prompt

            # --- 3. PARALLEL GENERATION ---
            v_ok, a_ok = await asyncio.gather(
                visual_provider.generate_video(refined_visual, raw_vid),
                audio_provider.generate(audio_script, audio, task.is_paid_voice)
            )

            if not v_ok:
                raise Exception("Video Generation Failed")

            # --- 4. STITCHING (UPDATED FOR MOCK FIX) ---
            if settings.USE_MOCK_VEO:
                logger.info("🚧 Mock Mode: Skipping FFmpeg stitch.")
                task.status = "COMPLETED (MOCK)"
                
                # FIX: Create a dummy file in the OUTPUT folder so the 404 goes away
                # If we have a raw mock video, copy it. If not, write dummy bytes.
                if raw_vid.exists():
                    shutil.copy(raw_vid, final)
                else:
                    with open(final, "wb") as f:
                        f.write(b"Mock Video File Content")
                
                task.final_output = str(final)
            else:
                self._stitch(raw_vid, audio, final)
                task.status = "COMPLETED"
                task.final_output = str(final)

        except Exception as e:
            logger.error(f"❌ Task Failed: {e}")
            task.status = "FAILED"
        finally:
            db.commit()
            db.close()

    def _stitch(self, video, audio, output):
        """
        Merges Audio and Video using FFmpeg.
        """
        has_audio = audio.exists() and os.path.getsize(audio) > 100

        if not has_audio:
            logger.warning("⚠️ Audio missing/empty. Creating silent video.")
            cmd = ["ffmpeg", "-i", str(video), "-c", "copy", "-y", str(output)]
        else:
            logger.info("🎞️ Stitching Audio + Video...")
            cmd = [
                "ffmpeg",
                "-stream_loop", "-1",   # Loop video
                "-i", str(video),       # Input 0
                "-i", str(audio),       # Input 1
                "-shortest",            # Stop when audio ends
                "-c:v", "libx264",      # Re-encode video
                "-c:a", "aac",          # Encode audio
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-y",
                str(output)
            ]
        
        # Run FFmpeg
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

orchestrator = Orchestrator()