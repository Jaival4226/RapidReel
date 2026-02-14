import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- PROJECT INFO ---
    PROJECT_NAME: str = "Foundry Pro"
    VERSION: str = "1.3.0"
    
    # --- API KEYS ---
    # Loads from .env
    LEONARDO_API_KEY: str = ""
    PEXELS_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    
    # --- MASTER SWITCHES ---
    # Options: "leonardo", "pexels", or "auto"
    VIDEO_PROVIDER: str = "auto" 
    
    USE_MOCK_VEO: bool = False       
    USE_MOCK_AUDIO: bool = False    

    # --- PATHS & STORAGE ---
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOCAL_STORAGE: str = os.path.join(os.path.dirname(BASE_DIR), "local_storage")

    @property
    def TEMP_PATH(self) -> Path:
        path = Path(self.LOCAL_STORAGE) / "temp"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def OUTPUT_PATH(self) -> Path:
        path = Path(self.LOCAL_STORAGE) / "outputs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def TEMP_DIR(self) -> Path:
        return self.TEMP_PATH

    @property
    def OUTPUT_DIR(self) -> Path:
        return self.OUTPUT_PATH

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()