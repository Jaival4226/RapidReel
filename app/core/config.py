import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Foundry Pro"
    PROJECT_ID: str = "ai-media-startup"  # <--- REPLACE THIS
    LOCATION: str = "us-central1"
    
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    OUTPUT_DIR: Path = BASE_DIR / "local_storage" / "outputs"
    TEMP_DIR: Path = BASE_DIR / "local_storage" / "temp"

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")

    # ⚠️ MASTER SWITCHES ⚠️
    USE_MOCK_VEO: bool = True       # Set to False for Real Video
    USE_MOCK_AUDIO: bool = False    # Set to False for Real Audio

    VEO_MODEL: str = "veo-2.0-generate-001"
    GEMINI_MODEL: str = "gemini-2.0-flash"

    def ensure_dirs(self):
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_dirs()