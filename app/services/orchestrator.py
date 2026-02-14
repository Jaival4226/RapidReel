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
        2. Audio Generation (EdgeTTS) & Subtitles (Whisper)
        3. Video Acquisition
        4. Branding & Stitching (Watermark + Intro/Outro)
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
            audio_script = task.monologue.strip() if task.monologue else None
            
            if audio_script:
                logger.info(f"🎤 Generating Audio...")
                # We await this because edge-tts is async
                await audio_provider.generate(audio_script, audio, task.is_paid_voice)
                
                # Transcribe ONLY if audio was successfully created
                if audio.exists() and os.path.getsize(audio) > 100:
                    logger.info("📝 Generating Subtitles...")
                    subtitle_file = await asyncio.to_thread(audio_provider.transcribe, audio)
            else:
                logger.info("🔇 No Audio Script. Skipping Audio & Subtitles.")
                if audio.exists(): os.remove(audio)

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
                # Ensure we have the code for this from previous steps
                refined_prompt = await visual_provider.refine(task.prompt, task.style)
                video_success = await visual_provider.generate_video(refined_prompt, raw_vid)
            else:
                # Mock fallback
                video_success = True 
                if not raw_vid.exists(): self._handle_mock(raw_vid, final)

            if not video_success and not settings.USE_MOCK_VEO:
                raise Exception(f"Video Generation failed with provider: {provider}")

            # ====================================================
            # 3. BRANDING & STITCHING
            # ====================================================
            if settings.USE_MOCK_VEO:
                self._handle_mock(raw_vid, final)
                task.status = "COMPLETED (MOCK)"
            else:
                logger.info("💎 Applying Brand Guard (Watermark, Intro, Outro)...")
                # We pass the 'task' object so we can check user preferences (task.use_watermark, etc)
                self._stitch_and_brand(raw_vid, audio, final, subtitle_file, task)
                
                task.status = "COMPLETED"
                task.final_output = str(final)

        except Exception as e:
            logger.error(f"❌ Task Failed: {e}", exc_info=True)
            task.status = "FAILED"
            task.error_msg = str(e)
        finally:
            db.commit()
            db.close()

    def _stitch_and_brand(self, video_path: Path, audio_path: Path, output_path: Path, subtitles_path: Path = None, task=None):
        """
        Two-Pass Pipeline:
        1. Core Processing: (Video + Audio + Subs + Watermark) -> temp_core.mp4
        2. Concatenation: (Intro + temp_core + Outro) -> Final.mp4
        """
        # Temporary core file (Video + Subs + Watermark)
        core_branded_path = video_path.parent / f"{video_path.stem}_core.mp4"
        
        has_audio = audio_path.exists() and os.path.getsize(audio_path) > 100
        
        # --- CHECK USER PREFERENCES ---
        # Only apply if file exists AND user checked the box
        has_watermark = settings.WATERMARK_FILE.exists() and (task.use_watermark if task else False)
        has_intro = settings.INTRO_FILE.exists() and (task.use_intro if task else False)
        has_outro = settings.OUTRO_FILE.exists() and (task.use_outro if task else False)

        # ---------------------------------------------------------
        # PASS 1: CORE PROCESSING (Resolution, Subs, Watermark)
        # ---------------------------------------------------------
        input_args = ["-y", "-stream_loop", "-1", "-i", str(video_path)]
        if has_audio:
            input_args.extend(["-i", str(audio_path)])
        
        # Determine Watermark Input Index
        wm_idx = None
        if has_watermark:
            input_args.extend(["-i", str(settings.WATERMARK_FILE)])
            wm_idx = 2 if has_audio else 1

        # Build Filter Complex
        filter_complex = []
        last_vid_label = "[0:v]"

        # 1. Scale to Standard 720p (Crucial for Intro/Outro matching)
        filter_complex.append(f"{last_vid_label}scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2[v_scaled]")
        last_vid_label = "[v_scaled]"

        # 2. Burn Subtitles
        if subtitles_path and subtitles_path.exists():
            sub_path_esc = str(subtitles_path).replace("\\", "/").replace(":", "\\:")
            # Yellow Text, Black Outline, Bottom Center
            style = "Fontname=Arial,FontSize=20,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=3,Outline=1,MarginV=25"
            filter_complex.append(f"{last_vid_label}subtitles='{sub_path_esc}':force_style='{style}'[v_subbed]")
            last_vid_label = "[v_subbed]"

        # 3. Apply Watermark
        if has_watermark:
            # Scale watermark to 150px wide, overlay top-right with padding
            filter_complex.append(f"[{wm_idx}:v]scale=150:-1[wm];{last_vid_label}[wm]overlay=main_w-overlay_w-20:20[v_final_core]")
            last_vid_label = "[v_final_core]"
        else:
            # Just alias the last label to final
            filter_complex.append(f"{last_vid_label}null[v_final_core]")

        # Execute Pass 1
        cmd_pass1 = ["ffmpeg", *input_args, "-filter_complex", ";".join(filter_complex), "-map", "[v_final_core]"]
        
        if has_audio:
            cmd_pass1.extend(["-map", "1:a", "-shortest"]) # Map audio from input 1
            cmd_pass1.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            # If no audio, generate silent audio track (needed for concatenation later)
            # This is complex in one pass, so for simplicity we just output video-only here 
            # and handle silence in Pass 2 if needed.
            pass

        cmd_pass1.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", str(core_branded_path)])
        
        logger.info("⚙️ Pass 1: Rendering Core Video (Subs + Watermark)...")
        subprocess.run(cmd_pass1, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        # ---------------------------------------------------------
        # PASS 2: CONCATENATION (Intro + Core + Outro)
        # ---------------------------------------------------------
        if not has_intro and not has_outro:
            # No bumpers? Just rename core to final
            if core_branded_path.exists():
                shutil.move(core_branded_path, output_path)
            return

        # If we have Intro/Outro, we MUST perform a concat
        # We use a filter_complex concat which re-encodes (safest for stability)
        
        concat_inputs = ["-y"]
        concat_filters = []
        input_count = 0
        
        # 1. Intro
        if has_intro:
            concat_inputs.extend(["-i", str(settings.INTRO_FILE)])
            # Scale & standard format
            concat_filters.append(f"[{input_count}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v{input_count}]")
            # We assume intro has audio. If not, this might fail unless we add a dummy audio generation.
            # For this 'Pro' version, let's assume assets are valid MP4s with audio.
            input_count += 1

        # 2. Core
        concat_inputs.extend(["-i", str(core_branded_path)])
        concat_filters.append(f"[{input_count}:v]setsar=1[v{input_count}]")
        input_count += 1

        # 3. Outro
        if has_outro:
            concat_inputs.extend(["-i", str(settings.OUTRO_FILE)])
            concat_filters.append(f"[{input_count}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v{input_count}]")
            input_count += 1

        # Concat Command
        # [v0][0:a][v1][1:a]... concat ...
        # Note: If core has no audio, we can't easily map [1:a]. 
        # Robust Logic: Only concat VIDEO streams for now to prevent crashes on silent clips.
        # Adding audio concat requires ensuring all inputs have audio streams.
        
        video_maps = "".join([f"[v{i}]" for i in range(input_count)])
        
        # Simple Video Concat (Audio is tricky without knowing if assets have sound)
        # We will try to map audio if available, but fallback to video-only concat if complex.
        # For this version: Video Concat + Core Audio (if exists) mapping is simplest.
        
        # Construct filter: [v0][v1][v2]concat=n=3:v=1:a=0[outv]
        concat_filters.append(f"{video_maps}concat=n={input_count}:v=1:a=0[outv]")

        cmd_pass2 = ["ffmpeg", *concat_inputs, "-filter_complex", ";".join(concat_filters), "-map", "[outv]"]
        
        # Map audio from Core (Index 1 if Intro exists, Index 0 if no Intro)
        # This is a bit hacky but preserves the main narration.
        # Ideally, intro/outro should have their own audio concatenated.
        core_idx = 1 if has_intro else 0
        if has_audio:
             cmd_pass2.extend(["-map", f"{core_idx}:a"])
        
        cmd_pass2.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)])
        
        logger.info("🔗 Pass 2: Concatenating Intro/Outro...")
        subprocess.run(cmd_pass2, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def _handle_mock(self, raw, final):
        if raw.exists():
            shutil.copy(raw, final)
        else:
            with open(final, "wb") as f:
                f.write(b"Mock Video Content")

orchestrator = Orchestrator()