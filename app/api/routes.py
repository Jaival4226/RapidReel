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

# --- INPUT SCHEMA ---
class TaskCreate(BaseModel):
    prompt: str
    monologue: Optional[str] = ""
    style: Optional[str] = "cinematic"
    is_paid_voice: Optional[bool] = False
    
    # --- BRANDING TOGGLES ---
    use_watermark: Optional[bool] = False
    use_intro: Optional[bool] = False
    use_outro: Optional[bool] = False

# --- OUTPUT SCHEMA ---
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

    class Config:
        from_attributes = True

# --- ENDPOINTS ---

@router.post("/generate")
def create_task(req: TaskCreate, bg: BackgroundTasks, db: Session = Depends(get_db)):
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

@router.get("/tasks", response_model=List[TaskSchema])
def list_tasks(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    return tasks

@router.get("/tasks/{task_id}")
def get_status(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "status": task.status,
        "final_output": task.final_output
    }

# --- THE FIXED UPLOAD ENDPOINT ---
@router.post("/upload-assets")
async def upload_brand_assets(
    intro: UploadFile = File(None),
    outro: UploadFile = File(None),
    watermark: UploadFile = File(None)
):
    try:
        # 1. FORCE CREATE THE DIRECTORY
        settings.ASSETS_PATH.mkdir(parents=True, exist_ok=True)
        
        status_msg = []

        # 2. SAVE FILES IF UPLOADED
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
        print(f"UPLOAD ERROR: {e}") # Print error to terminal
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")