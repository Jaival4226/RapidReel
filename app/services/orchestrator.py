import asyncio
import subprocess
import logging
import os
import shutil
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.config import settings

# --- PROVIDERS ---
from app.providers.audio import audio_provider
from app.providers.visual import visual_provider, stock_provider
from app.services.router import decision_engine

# --- DATABASE ---
from app.db.models import Task
from app.db.session import SessionLocal

logger = logging.getLogger("Foundry.Orchestrator")

class Orchestrator:
    async def process_task(self, task_id: str):
        """
        Full Pipeline:
        1. Router (Auto/Pexels/Leonardo)
        2. Audio Generation (Strict Check)
        3. Subtitle Transcription
        4. Video Acquisition
        5. Stitching (Burned Subtitles)
        """
        db: Session = SessionLocal()
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            logger.error(f"❌ Task {task_id} not found in DB.")
            return

        try:
            # --- UPDATE STATUS: PROCESSING ---
            logger.info(f"🚀 Starting Task {task_id}")
            task.status = "PROCESSING"
            db.commit()
            
            # --- DEFINE PATHS ---
            raw_vid = settings.TEMP_DIR / f"{task_id}_raw.mp4"
            audio = settings.TEMP_DIR / f"{task_id}.mp3"
            final = settings.OUTPUT_DIR / f"{task_id}_final.mp4"
            subtitle_file = None

            # ====================================================
            # 1. AUDIO & SUBTITLES
            # ====================================================
            # Strict Check: Only generate if monologue exists and is not just spaces
            audio_script = task.monologue.strip() if task.monologue else None
            
            if audio_script:
                logger.info(f"🎤 Generating Audio for: '{audio_script[:20]}...'")
                await audio_provider.generate(audio_script, audio, task.is_paid_voice)
                
                # Transcribe ONLY if audio was created
                if audio.exists() and os.path.getsize(audio) > 100:
                    logger.info("📝 Generatng Subtitles...")
                    # Run in thread to avoid blocking the event loop
                    subtitle_file = await asyncio.to_thread(audio_provider.transcribe, audio)
            else:
                logger.info("🔇 No Audio Script. Skipping Audio & Subtitles.")
                # Ensure no stale audio file exists from previous runs
                if audio.exists():
                    os.remove(audio)

            # ====================================================
            # 2. VISUAL ENGINE (ROUTER)
            # ====================================================
            provider = settings.VIDEO_PROVIDER
            
            if provider == "auto":
                logger.info("🧠 Mode: AUTO. Consulting Decision Engine...")
                provider = await asyncio.to_thread(decision_engine.decide_provider, task.prompt)
                logger.info(f"🤖 Engine Selected: {provider.upper()}")

            # Execution
            video_success = False
            if provider == "pexels":
                video_success = await stock_provider.search_and_download(task.prompt, raw_vid)
            elif provider == "leonardo":
                refined_prompt = await visual_provider.refine(task.prompt, task.style)
                video_success = await visual_provider.generate_video(refined_prompt, raw_vid)
            else:
                logger.warning(f"⚠️ Unknown Provider: {provider}. Defaulting to Mock.")
                # Mock logic for safety
                video_success = True 
                if not raw_vid.exists():
                    self._handle_mock(raw_vid, final)

            if not video_success and not settings.USE_MOCK_VEO:
                raise Exception(f"Video Generation failed with provider: {provider}")

            # ====================================================
            # 3. STITCHING & BRANDING
            # ====================================================
            if settings.USE_MOCK_VEO:
                logger.info("🚧 Mock Mode: Skipping Stitch.")
                self._handle_mock(raw_vid, final)
                task.status = "COMPLETED (MOCK)"
            else:
                logger.info("🎞️ Stitching Final Video...")
                self._stitch(raw_vid, audio, final, subtitle_file)
                task.status = "COMPLETED"
                task.final_output = str(final)

        except Exception as e:
            logger.error(f"❌ Task Failed: {e}", exc_info=True)
            task.status = "FAILED"
            task.error_msg = str(e)
        finally:
            db.commit()
            db.close()

    def _stitch(self, video, audio, output, subtitles=None):
        """
        Merges Video, Audio, and Subtitles (Burn-in).
        """
        inputs = ["-stream_loop", "-1", "-i", str(video)]
        has_audio = audio.exists() and os.path.getsize(audio) > 100
        
        if has_audio:
            inputs.extend(["-i", str(audio)])

        # --- FILTER CHAIN (SUBTITLES) ---
        vf_chain = []
        if subtitles and subtitles.exists():
            # FFmpeg needs escaped paths for Windows/Linux compatibility in filter strings
            sub_path = str(subtitles).replace("\\", "/").replace(":", "\\:")
            # TikTok/Reels Style: Yellow Text, Black Outline, Bottom Center
            style = (
                "Fontname=Arial,FontSize=20,PrimaryColour=&H00FFFF,OutlineColour=&H000000,"
                "BorderStyle=3,Outline=1,Shadow=0,MarginV=20"
            )
            vf_chain.append(f"subtitles='{sub_path}':force_style='{style}'")

        # Build Command
        cmd = ["ffmpeg", "-y", *inputs]
        
        # Audio/Video Mapping
        if has_audio:
            cmd.append("-shortest") # Cut video to audio length
        else:
            # If no audio, we can't use -shortest reliably without an audio stream
            # So we might want to just limit duration or keep original video length
            pass 

        # Apply Filters
        if vf_chain:
            cmd.extend(["-vf", ",".join(vf_chain)])

        # Output Codecs
        cmd.extend([
            "-c:v", "libx264",
            "-c:a", "aac" if has_audio else "copy", 
            "-pix_fmt", "yuv420p", # Essential for QuickTime/Windows support
            str(output)
        ])
        
        # Remove audio track if silence was requested but video had sound
        if not has_audio:
             # This ensures we don't keep the stock footage audio if we wanted silence
            cmd.insert(cmd.index("-c:v"), "-an")

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def _handle_mock(self, raw, final):
        if raw.exists():
            shutil.copy(raw, final)
        else:
            with open(final, "wb") as f:
                f.write(b"Mock Video Content")

orchestrator = Orchestrator()