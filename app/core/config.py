import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- PROJECT INFO ---
    PROJECT_NAME: str = "Foundry Pro"
    VERSION: str = "1.5.0"
    
    # --- API KEYS ---
    LEONARDO_API_KEY: str = ""
    PEXELS_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    
    # --- MASTER SWITCHES ---
    VIDEO_PROVIDER: str = "leonardo" 
    USE_MOCK_VEO: bool = False       
    USE_MOCK_AUDIO: bool = False    

    # --- PATHS & STORAGE ---
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOCAL_STORAGE: str = os.path.join(os.path.dirname(BASE_DIR), "local_storage")

    # --- DYNAMIC PATHS (Temp & Output) ---
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
    def TEMP_DIR(self) -> Path: return self.TEMP_PATH

    @property
    def OUTPUT_DIR(self) -> Path: return self.OUTPUT_PATH

    # --- BRAND ASSETS (CRITICAL FOR UPLOAD) ---
    @property
    def ASSETS_PATH(self) -> Path:
        path = Path(self.LOCAL_STORAGE) / "assets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def INTRO_FILE(self) -> Path: return self.ASSETS_PATH / "intro.mp4"

    @property
    def OUTRO_FILE(self) -> Path: return self.ASSETS_PATH / "outro.mp4"

    @property
    def WATERMARK_FILE(self) -> Path: return self.ASSETS_PATH / "watermark.png"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()