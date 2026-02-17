import uuid
import shutil
from typing import List, Optional, Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import Task
from app.services.orchestrator import orchestrator
from app.core.config import settings

router = APIRouter()

# ==========================================
# 0. DATA STRUCTURES (Optimization)
# ==========================================

# 1. SET: Efficient O(1) lookup for validation
VALID_STYLES = {
    "cinematic", "anime", "photorealistic", "noir", "cyberpunk"
}

# ==========================================
# 1. DATA MODELS
# ==========================================

class TaskCreate(BaseModel):
    prompt: str
    monologue: Optional[str] = ""
    style: Optional[str] = "cinematic"
    is_paid_voice: Optional[bool] = False
    use_watermark: Optional[bool] = False
    use_intro: Optional[bool] = False
    use_outro: Optional[bool] = False
    use_subtitles: Optional[bool] = True # Added

class RemixPayload(BaseModel):
    prompt: str
    monologue: str
    style: str
    is_paid_voice: bool
    use_watermark: bool
    use_intro: bool
    use_outro: bool
    use_subtitles: bool # Added
    
    # Instruction Flags
    regenerate_video: bool 
    regenerate_audio: bool

class TaskSchema(BaseModel):
    id: str
    prompt: str
    monologue: Optional[str] = None
    style: Optional[str] = "cinematic"
    is_paid_voice: bool
    status: str
    final_output: Optional[str] = None
    created_at: Any = None 
    use_watermark: Optional[bool] = False
    use_intro: Optional[bool] = False
    use_outro: Optional[bool] = False
    use_subtitles: Optional[bool] = True # Added
    class Config: from_attributes = True

# ==========================================
# 2. ENDPOINTS
# ==========================================

@router.post("/generate")
def create_task(req: TaskCreate, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Start a fresh video generation task."""
    
    # Validation using Data Structure (Set)
    # We don't block invalid styles, but we default them safely without complex if-else chains
    if req.style not in VALID_STYLES:
        req.style = "cinematic"

    task_id = str(uuid.uuid4())
    new_task = Task(
        id=task_id, 
        prompt=req.prompt, 
        monologue=req.monologue,
        style=req.style, 
        is_paid_voice=req.is_paid_voice,
        status="QUEUED",
        use_watermark=req.use_watermark,
        use_intro=req.use_intro,
        use_outro=req.use_outro,
        use_subtitles=req.use_subtitles
    )
    try:
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {e}")

    bg.add_task(orchestrator.process_task, task_id)
    return {"task_id": task_id, "status": "QUEUED"}

@router.post("/remix/{task_id}")
def remix_task(task_id: str, req: RemixPayload, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Edit an existing task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Update Database
    task.prompt = req.prompt
    task.monologue = req.monologue
    task.style = req.style
    task.is_paid_voice = req.is_paid_voice
    task.use_watermark = req.use_watermark
    task.use_intro = req.use_intro
    task.use_outro = req.use_outro
    task.use_subtitles = req.use_subtitles
    
    task.status = "REMIXING"
    
    try:
        db.commit()
        db.refresh(task)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB Update Failed: {e}")

    bg.add_task(orchestrator.remix_task, task_id, req.dict())
    return {"task_id": task_id, "status": "REMIXING"}

@router.get("/tasks", response_model=List[TaskSchema])
def list_tasks(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """Fetch gallery items."""
    return db.query(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/tasks/{task_id}")
def get_status(task_id: str, db: Session = Depends(get_db)):
    """Fetch single item status."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "status": task.status,
        "final_output": task.final_output,
        "prompt": task.prompt,
        "monologue": task.monologue,
        "style": task.style,
        "is_paid_voice": task.is_paid_voice,
        "use_watermark": task.use_watermark,
        "use_intro": task.use_intro,
        "use_outro": task.use_outro,
        "use_subtitles": task.use_subtitles
    }

@router.post("/upload-assets")
async def upload_brand_assets(
    intro: UploadFile = File(None),
    outro: UploadFile = File(None),
    watermark: UploadFile = File(None)
):
    """Upload branding files using a Dictionary map."""
    try:
        settings.ASSETS_PATH.mkdir(parents=True, exist_ok=True)
        status_msg = []

        # 2. DICTIONARY: Maps input fields to destination paths
        # This replaces repetitive 'if x: save x' blocks
        asset_map = {
            "intro": {"file": intro, "dest": settings.INTRO_FILE, "msg": "Intro updated"},
            "outro": {"file": outro, "dest": settings.OUTRO_FILE, "msg": "Outro updated"},
            "watermark": {"file": watermark, "dest": settings.WATERMARK_FILE, "msg": "Watermark updated"}
        }

        # Iterate through dictionary
        for key, data in asset_map.items():
            upload_obj = data["file"]
            if upload_obj:
                with open(data["dest"], "wb") as buffer:
                    shutil.copyfileobj(upload_obj.file, buffer)
                status_msg.append(data["msg"])

        if not status_msg:
            return {"message": "No files received."}

        return {"message": ", ".join(status_msg), "status": "success"}

    except Exception as e:
        print(f"UPLOAD ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")