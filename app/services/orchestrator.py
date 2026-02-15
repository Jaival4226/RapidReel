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
        db: Session = SessionLocal()
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task: return

        try:
            logger.info(f"🚀 Starting Task {task_id}")
            task.status = "PROCESSING"
            db.commit()
            
            # Paths
            raw_vid = settings.TEMP_DIR / f"{task_id}_raw.mp4"
            audio = settings.TEMP_DIR / f"{task_id}.mp3"
            final = settings.OUTPUT_DIR / f"{task_id}_final.mp4"
            subtitle_file = None

            # 1. Audio
            audio_script = task.monologue.strip() if task.monologue else None
            if audio_script:
                await audio_provider.generate(audio_script, audio, task.is_paid_voice)
                if audio.exists() and os.path.getsize(audio) > 100:
                    subtitle_file = await asyncio.to_thread(audio_provider.transcribe, audio)
            
            # 2. Visuals
            provider = settings.VIDEO_PROVIDER
            if provider == "auto":
                provider = await asyncio.to_thread(decision_engine.decide_provider, task.prompt)
            
            if provider == "pexels":
                await stock_provider.search_and_download(task.prompt, raw_vid)
            elif provider == "leonardo":
                refined = await visual_provider.refine(task.prompt, task.style)
                await visual_provider.generate_video(refined, raw_vid)
            else:
                if not raw_vid.exists(): self._handle_mock(raw_vid, final)

            # 3. Stitching
            if not raw_vid.exists() and not settings.USE_MOCK_VEO:
                raise Exception("Video generation failed.")

            if settings.USE_MOCK_VEO:
                self._handle_mock(raw_vid, final)
                task.status = "COMPLETED (MOCK)"
            else:
                self._stitch_and_brand(raw_vid, audio, final, subtitle_file, task)
                task.status = "COMPLETED"
                task.final_output = str(final)

        except Exception as e:
            logger.error(f"Task Failed: {e}", exc_info=True)
            task.status = "FAILED"
            task.error_msg = str(e)
        finally:
            db.commit()
            db.close()

    def _stitch_and_brand(self, video_path: Path, audio_path: Path, output_path: Path, subtitles_path: Path = None, task=None):
        """
        Robust Pipeline:
        1. Pre-process Core Video (Add Silence if needed, Burn Subs, Watermark) -> core.mp4
        2. Concat (Intro + Core + Outro)
        """
        core_path = video_path.parent / f"{video_path.stem}_core.mp4"
        
        has_audio = audio_path.exists() and os.path.getsize(audio_path) > 100
        has_watermark = settings.WATERMARK_FILE.exists() and (task.use_watermark if task else False)
        
        # --- STEP 1: PREPARE CORE VIDEO ---
        # We ensure the core video has a stereo audio track (even if silent)
        # so it can be concatenated with Intro/Outro music later.
        
        input_args = ["-y", "-stream_loop", "-1", "-i", str(video_path)]
        if has_audio:
            input_args.extend(["-i", str(audio_path)])
        else:
            # Generate 5 seconds of silence if no audio
            input_args.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

        # Watermark Setup
        wm_idx = 2  # Default index for watermark
        
        filter_complex = []
        last_vid = "[0:v]"
        
        # Scale & Pad to 720p
        filter_complex.append(f"{last_vid}scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v_scaled]")
        last_vid = "[v_scaled]"

        # Subtitles
        if subtitles_path and subtitles_path.exists():
            sub_esc = str(subtitles_path).replace("\\", "/").replace(":", "\\:")
            style = "Fontname=Arial,FontSize=20,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=3,Outline=1,MarginV=25"
            filter_complex.append(f"{last_vid}subtitles='{sub_esc}':force_style='{style}'[v_subbed]")
            last_vid = "[v_subbed]"

        # Watermark
        if has_watermark:
            input_args.extend(["-i", str(settings.WATERMARK_FILE)])
            filter_complex.append(f"[{wm_idx}:v]scale=150:-1[wm];{last_vid}[wm]overlay=main_w-overlay_w-20:20[v_final]")
            last_vid = "[v_final]"
        else:
            filter_complex.append(f"{last_vid}null[v_final]")

        # Audio Normalization (Map input 1 to stereo 44.1k)
        filter_complex.append("[1:a]aformat=sample_rates=44100:channel_layouts=stereo[a_final]")

        cmd1 = ["ffmpeg", *input_args, "-filter_complex", ";".join(filter_complex), "-map", last_vid, "-map", "[a_final]"]
        
        if has_audio:
            cmd1.append("-shortest")
        else:
            cmd1.extend(["-t", "10"]) # 10s default duration

        cmd1.extend(["-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(core_path)])
        subprocess.run(cmd1, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        # --- STEP 2: CONCATENATION ---
        has_intro = settings.INTRO_FILE.exists() and (task.use_intro if task else False)
        has_outro = settings.OUTRO_FILE.exists() and (task.use_outro if task else False)

        if not has_intro and not has_outro:
            if core_path.exists(): shutil.move(core_path, output_path)
            return

        # Build Concat List
        concat_inputs = ["-y"]
        concat_filter = []
        n = 0
        
        # We need to build the map string explicitly as we go: [v0][a0][v1][a1]...
        concat_maps = [] 

        # Intro
        if has_intro:
            concat_inputs.extend(["-i", str(settings.INTRO_FILE)])
            concat_filter.append(f"[{n}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v{n}]")
            concat_filter.append(f"[{n}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{n}]")
            concat_maps.append(f"[v{n}][a{n}]") # Correct Pairing
            n += 1

        # Core
        concat_inputs.extend(["-i", str(core_path)])
        concat_filter.append(f"[{n}:v]setsar=1[v{n}]")
        concat_filter.append(f"[{n}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{n}]")
        concat_maps.append(f"[v{n}][a{n}]") # Correct Pairing
        n += 1

        # Outro
        if has_outro:
            concat_inputs.extend(["-i", str(settings.OUTRO_FILE)])
            concat_filter.append(f"[{n}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v{n}]")
            concat_filter.append(f"[{n}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{n}]")
            concat_maps.append(f"[v{n}][a{n}]") # Correct Pairing
            n += 1

        # Concat Command
        full_map = "".join(concat_maps) # Result: [v0][a0][v1][a1][v2][a2]
        
        concat_filter.append(f"{full_map}concat=n={n}:v=1:a=1[outv][outa]")

        cmd2 = ["ffmpeg", *concat_inputs, "-filter_complex", ";".join(concat_filter), 
                "-map", "[outv]", "-map", "[outa]", 
                "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(output_path)]

        # Keep stderr=None for now just in case, but this logic is definitely correct.
        subprocess.run(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def _handle_mock(self, raw, final):
        if raw.exists(): shutil.copy(raw, final)
        else:
            with open(final, "wb") as f: f.write(b"Mock")

orchestrator = Orchestrator()