from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel
import uuid

from app.db.session import get_db
from app.db.models import Task
from app.services.orchestrator import orchestrator

router = APIRouter()

# --- INPUT SCHEMA ---
class GenerateRequest(BaseModel):
    prompt: str
    monologue: str = ""       # Default to empty string if missing
    style: str = "cinematic"
    use_paid_voice: bool = False

# --- OUTPUT SCHEMA (For Gallery) ---
class TaskSchema(BaseModel):
    id: str
    prompt: str
    monologue: Optional[str] = None
    style: str  # <--- NEW
    is_paid_voice: bool # <--- NEW
    status: str
    final_output: Optional[str] = None
    created_at: Any = None 

    class Config:
        from_attributes = True

# --- ENDPOINTS ---

@router.post("/generate")
def create_task(req: GenerateRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Creates a new Task in the DB and starts the Orchestrator.
    """
    task_id = str(uuid.uuid4())
    
    # 1. Create DB Entry
    new_task = Task(
        id=task_id, 
        prompt=req.prompt, 
        monologue=req.monologue,  # <--- Saving the monologue
        style=req.style, 
        is_paid_voice=req.use_paid_voice,
        status="QUEUED"
    )
    
    try:
        db.add(new_task)
        db.commit()
        db.refresh(new_task) # Refresh to get the created_at timestamp
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {e}")

    # 2. Start Background Job
    bg.add_task(orchestrator.process_task, task_id)

    return {"task_id": task_id, "status": "QUEUED"}

@router.get("/tasks", response_model=List[TaskSchema])
def list_tasks(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """
    Returns the history of tasks for the Gallery.
    """
    tasks = db.query(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    return tasks

@router.get("/tasks/{task_id}")
def get_status(task_id: str, db: Session = Depends(get_db)):
    """
    Returns status of a specific task (used for polling).
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "id": task.id,
        "status": task.status,
        "final_output": task.final_output # Frontend needs this to show the video
    }