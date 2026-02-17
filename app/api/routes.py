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

class RemixPayload(BaseModel):
    # Data Fields
    prompt: str
    monologue: str
    style: str
    is_paid_voice: bool
    use_watermark: bool
    use_intro: bool
    use_outro: bool
    
    # Instruction Flags (The key to the new logic)
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
    class Config: from_attributes = True

# ==========================================
# 2. ENDPOINTS
# ==========================================

@router.post("/generate")
def create_task(req: TaskCreate, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Start a fresh video generation task."""
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
        use_outro=req.use_outro
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
    """Edit an existing task with explicit regeneration flags."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # A. Update Database (Instant Save)
    task.prompt = req.prompt
    task.monologue = req.monologue
    task.style = req.style
    task.is_paid_voice = req.is_paid_voice
    task.use_watermark = req.use_watermark
    task.use_intro = req.use_intro
    task.use_outro = req.use_outro
    
    task.status = "REMIXING"
    
    try:
        db.commit()
        db.refresh(task)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB Update Failed: {e}")

    # B. Trigger Background Job
    # We pass the flags (req.dict()) so the orchestrator knows what to regenerate.
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
        "use_outro": task.use_outro
    }

@router.post("/upload-assets")
async def upload_brand_assets(
    intro: UploadFile = File(None),
    outro: UploadFile = File(None),
    watermark: UploadFile = File(None)
):
    """Upload branding files to the assets folder."""
    try:
        settings.ASSETS_PATH.mkdir(parents=True, exist_ok=True)
        status_msg = []

        if intro:
            with open(settings.INTRO_FILE, "wb") as buffer:
                shutil.copyfileobj(intro.file, buffer)
            status_msg.append("Intro updated")

        if outro:
            with open(settings.OUTRO_FILE, "wb") as buffer:
                shutil.copyfileobj(outro.file, buffer)
            status_msg.append("Outro updated")

        if watermark:
            with open(settings.WATERMARK_FILE, "wb") as buffer:
                shutil.copyfileobj(watermark.file, buffer)
            status_msg.append("Watermark updated")

        if not status_msg:
            return {"message": "No files received."}

        return {"message": ", ".join(status_msg), "status": "success"}

    except Exception as e:
        print(f"UPLOAD ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")