import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- PROJECT INFO ---
    PROJECT_NAME: str = "Foundry Pro"
    VERSION: str = "1.0.0"
    
    # --- API KEYS ---
    LEONARDO_API_KEY: str = "00cc04d3-9d6d-484d-81e7-d025238300ed"
    KIE_API_KEY: str = "61b926761ea72259108666e13366cba9"  # <--- NEW KEY
    
    # --- MASTER SWITCHES ---
    # Options: "kie" (Sora 2) or "leonardo" (Motion 2.0)
    VIDEO_PROVIDER: str = "kie"  # <--- CHANGE THIS TO SWITCH ENGINES
    
    USE_MOCK_VEO: bool = False       
    USE_MOCK_AUDIO: bool = False    

    # --- PATHS & STORAGE ---
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOCAL_STORAGE: str = os.path.join(os.path.dirname(BASE_DIR), "local_storage")

    # --- DYNAMIC PATH PROPERTIES ---
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

settings = Settings()
