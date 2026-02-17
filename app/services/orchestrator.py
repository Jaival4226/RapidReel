import asyncio
import subprocess
import logging
import os
import shutil
import uuid
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.config import settings

from app.providers.audio import audio_provider
from app.providers.visual import visual_provider, stock_provider
from app.services.router import decision_engine
from app.db.models import Task
from app.db.session import SessionLocal

logger = logging.getLogger("RapidReel.Orchestrator")

class Orchestrator:
    # ---------------------------------------------------------
    # 1. FRESH GENERATION
    # ---------------------------------------------------------
    async def process_task(self, task_id: str):
        db: Session = SessionLocal()
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task: return

        try:
            logger.info(f"🚀 Starting Task {task_id}")
            task.status = "PROCESSING"
            db.commit()
            
            raw_vid = settings.TEMP_DIR / f"{task_id}_raw.mp4"
            audio = settings.TEMP_DIR / f"{task_id}.mp3"
            final = settings.OUTPUT_DIR / f"{task_id}_final.mp4"
            subtitle_file = None

            # Audio
            if task.monologue:
                await audio_provider.generate(task.monologue, audio, task.is_paid_voice)
                if audio.exists() and os.path.getsize(audio) > 100:
                    subtitle_file = await asyncio.to_thread(audio_provider.transcribe, audio)
            
            # Visuals
            provider = settings.VIDEO_PROVIDER
            if provider == "auto":
                provider = await asyncio.to_thread(decision_engine.decide_provider, task.prompt)
            
            if provider == "pexels":
                await stock_provider.search_and_download(task.prompt, raw_vid)
            elif provider == "leonardo":
                refined_prompt = await asyncio.to_thread(decision_engine.refine_for_leonardo, task.prompt)
                await visual_provider.generate_video(refined_prompt, raw_vid)
            else:
                if not raw_vid.exists(): self._handle_mock(raw_vid, final)

            if not raw_vid.exists() and not settings.USE_MOCK_VEO:
                raise Exception("Video generation failed.")

            self._stitch_and_brand(raw_vid, audio, final, subtitle_file, task.use_watermark, task.use_intro, task.use_outro, task.use_subtitles)
            
            task.status = "COMPLETED"
            task.final_output = str(final)

        except Exception as e:
            logger.error(f"Task Failed: {e}", exc_info=True)
            task.status = "FAILED"
            task.error_msg = str(e)
        finally:
            db.commit()
            db.close()

    # ---------------------------------------------------------
    # 2. REMIX ENGINE
    # ---------------------------------------------------------
    async def remix_task(self, task_id: str, payload: dict):
        db: Session = SessionLocal()
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task: return

        try:
            print(f"🎛️ REMIXING {task_id}")
            
            raw_vid = settings.TEMP_DIR / f"{task_id}_raw.mp4"
            audio = settings.TEMP_DIR / f"{task_id}.mp3"
            final = settings.OUTPUT_DIR / f"{task_id}_final.mp4"
            subtitle_file = audio.with_suffix(".srt")

            # A. Visuals
            if payload['regenerate_video']:
                if raw_vid.exists(): os.remove(raw_vid)
                provider = settings.VIDEO_PROVIDER
                if provider == "auto":
                    provider = await asyncio.to_thread(decision_engine.decide_provider, payload['prompt'])
                if provider == "pexels":
                    await stock_provider.search_and_download(payload['prompt'], raw_vid)
                elif provider == "leonardo":
                    refined_prompt = await asyncio.to_thread(decision_engine.refine_for_leonardo, payload['prompt'])
                    await visual_provider.generate_video(refined_prompt, raw_vid)
            else:
                if not raw_vid.exists(): raise Exception("Raw video missing.")

            # B. Audio
            if payload['regenerate_audio']:
                remix_id = uuid.uuid4().hex[:6]
                new_audio = settings.TEMP_DIR / f"{task_id}_{remix_id}.mp3"
                if payload['monologue']:
                    success = await audio_provider.generate(payload['monologue'], new_audio, payload['is_paid_voice'])
                    if success:
                        await asyncio.to_thread(audio_provider.transcribe, new_audio)
                        audio = new_audio
                        subtitle_file = new_audio.with_suffix(".srt")
                        shutil.copy(new_audio, settings.TEMP_DIR / f"{task_id}.mp3")
                        if subtitle_file.exists(): shutil.copy(subtitle_file, settings.TEMP_DIR / f"{task_id}.srt")

            # C. Stitching
            self._stitch_and_brand(
                raw_vid, audio, final, 
                (subtitle_file if subtitle_file.exists() else None),
                payload['use_watermark'],
                payload['use_intro'],
                payload['use_outro'],
                payload['use_subtitles']
            )
            
            task.status = "COMPLETED"
            task.final_output = str(final)

        except Exception as e:
            logger.error(f"Remix Failed: {e}", exc_info=True)
            task.status = "FAILED"
            task.error_msg = str(e)
        finally:
            db.commit()
            db.close()

    # ---------------------------------------------------------
    # 3. SHARED PIPELINE (FFmpeg)
    # ---------------------------------------------------------
    def _stitch_and_brand(self, video_path, audio_path, output_path, subtitles_path, use_wm, use_in, use_out, use_subs):
        
        unique_core = f"{video_path.stem}_core_{uuid.uuid4().hex[:4]}.mp4"
        core_path = video_path.parent / unique_core
        
        has_audio = audio_path.exists() and os.path.getsize(audio_path) > 100
        apply_wm = settings.WATERMARK_FILE.exists() and use_wm

        input_args = ["-y", "-stream_loop", "-1", "-i", str(video_path)]
        if has_audio:
            input_args.extend(["-i", str(audio_path)])
        else:
            input_args.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

        filter_complex = []
        last_vid = "[0:v]"
        
        filter_complex.append(f"{last_vid}scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v_scaled]")
        last_vid = "[v_scaled]"

        if subtitles_path and use_subs:
            sub_esc = str(subtitles_path).replace("\\", "/").replace(":", "\\:")
            style = "Fontname=Arial,FontSize=24,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=3,Outline=2,MarginV=30"
            filter_complex.append(f"{last_vid}subtitles='{sub_esc}':force_style='{style}'[v_subbed]")
            last_vid = "[v_subbed]"

        if apply_wm:
            input_args.extend(["-i", str(settings.WATERMARK_FILE)])
            filter_complex.append(f"[2:v]scale=150:-1[wm];{last_vid}[wm]overlay=main_w-overlay_w-20:20[v_final]")
            last_vid = "[v_final]"
        else:
            filter_complex.append(f"{last_vid}null[v_final]")
            last_vid = "[v_final]"

        filter_complex.append("[1:a]aformat=sample_rates=44100:channel_layouts=stereo[a_final]")

        cmd1 = ["ffmpeg", *input_args, "-filter_complex", ";".join(filter_complex), "-map", last_vid, "-map", "[a_final]"]
        if has_audio: cmd1.append("-shortest")
        else: cmd1.extend(["-t", "10"])
        cmd1.extend(["-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(core_path)])
        
        subprocess.run(cmd1, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

        # -----------------------------------------------------
        # OPTIMIZED CONCATENATION LOGIC USING LISTS
        # -----------------------------------------------------
        
        if output_path.exists():
            os.remove(output_path)

        # 3. LIST: Dynamic build of clips sequence
        clips_to_process = []
        
        if settings.INTRO_FILE.exists() and use_in:
            clips_to_process.append({"file": settings.INTRO_FILE, "type": "intro"})
            
        clips_to_process.append({"file": core_path, "type": "main"})
        
        if settings.OUTRO_FILE.exists() and use_out:
            clips_to_process.append({"file": settings.OUTRO_FILE, "type": "outro"})

        # If only main video (no intro/outro), just move it
        if len(clips_to_process) == 1:
            if core_path.exists(): shutil.move(core_path, output_path)
            return

        concat_inputs = ["-y"]
        concat_filter = []
        concat_maps = []
        
        for n, clip in enumerate(clips_to_process):
            path = clip["file"]
            concat_inputs.extend(["-i", str(path)])
            
            if clip["type"] in ["intro", "outro"]:
                concat_filter.append(f"[{n}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v{n}]")
            else:
                concat_filter.append(f"[{n}:v]setsar=1[v{n}]")
                
            concat_filter.append(f"[{n}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{n}]")
            concat_maps.append(f"[v{n}][a{n}]")

        full_map = "".join(concat_maps)
        concat_filter.append(f"{full_map}concat=n={len(clips_to_process)}:v=1:a=1[outv][outa]")

        cmd2 = ["ffmpeg", *concat_inputs, "-filter_complex", ";".join(concat_filter), 
                "-map", "[outv]", "-map", "[outa]", 
                "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(output_path)]

        subprocess.run(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        
        if core_path.exists(): os.remove(core_path)

    def _handle_mock(self, raw, final):
        if raw.exists(): shutil.copy(raw, final)
        else:
            with open(final, "wb") as f: f.write(b"Mock")

orchestrator = Orchestrator()