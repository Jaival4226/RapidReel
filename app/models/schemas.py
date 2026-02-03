from pydantic import BaseModel
from typing import Optional

class VideoRequest(BaseModel):
    prompt: str
    sub_mode: str = "cinematic"
    use_paid_voice: bool = False # If True, forces ElevenLabs
    voice_style: str = "en-US-ChristopherNeural" # EdgeTTS voice ID

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str