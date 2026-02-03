import os
import sys
from pathlib import Path

# Fix imports to allow running from root directory
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.db.models import Task
from app.core.config import settings

def restore_orphaned_videos():
    """
    Scans the local_storage/outputs folder for video files
    and adds them back to the database if they are missing.
    """
    db = SessionLocal()
    output_dir = settings.OUTPUT_DIR
    
    # 1. Find all generated videos
    # Pattern is usually: {uuid}_final.mp4
    video_files = list(output_dir.glob("*_final.mp4"))
    
    print(f"📂 Scanning {output_dir}...")
    print(f"🎥 Found {len(video_files)} video files in storage.")

    restored_count = 0
    
    for file_path in video_files:
        # Extract ID from filename (e.g., "abc-123_final.mp4" -> "abc-123")
        filename = file_path.name
        task_id = filename.replace("_final.mp4", "")
        
        # 2. Check if this task already exists in DB
        exists = db.query(Task).filter(Task.id == task_id).first()
        
        if not exists:
            print(f"   ↳ Restoring missing task: {task_id[:8]}...")
            
            # 3. Create a Recovery Record
            # Since we lost the original prompt/monologue when deleting the DB,
            # we set placeholders.
            recovered_task = Task(
                id=task_id,
                prompt="[Restored from Archive]", 
                monologue="[Metadata Lost]",
                style="Unknown",
                status="COMPLETED",
                final_output=str(file_path),
                is_paid_voice=False
            )
            db.add(recovered_task)
            restored_count += 1
    
    db.commit()
    db.close()
    
    print("-" * 30)
    print(f"✅ Success! Restored {restored_count} videos to the Gallery.")

if __name__ == "__main__":
    restore_orphaned_videos()