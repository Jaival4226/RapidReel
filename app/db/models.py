from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.session import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    
    # Inputs
    prompt = Column(String, nullable=False)
    monologue = Column(String, nullable=True)  # <--- Ensure this exists
    style = Column(String, default="cinematic")
    is_paid_voice = Column(Boolean, default=False)
    
    # Process Status
    status = Column(String, default="QUEUED")  # QUEUED, PROCESSING, COMPLETED, FAILED
    
    # File Artifacts
    video_path = Column(String, nullable=True) # Raw video
    audio_path = Column(String, nullable=True) # Raw audio
    final_output = Column(String, nullable=True) # Stitched Result
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())