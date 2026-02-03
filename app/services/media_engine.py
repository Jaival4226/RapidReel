import subprocess
from pathlib import Path
from app.core.logging import setup_logging

logger = setup_logging("Foundry-FFmpeg")

class MediaEngine:
    def stitch_av(self, video_path: Path, audio_path: Path, output_path: Path):
        """
        Merges Audio and Video. 
        Loops the video to match audio duration.
        """
        cmd = [
            "ffmpeg",
            "-stream_loop", "-1",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-shortest",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264", 
            "-c:a", "aac",
            "-y", 
            str(output_path)
        ]
        
        try:
            logger.info(f"🎞️ Stitching media: {output_path.name}")
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg Error: {e}")
            return False

media_engine = MediaEngine()