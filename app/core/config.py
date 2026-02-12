# app/core/config.py
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Foundry Pro"
    
    # 🎨 LEONARDO AI SETTINGS
    # Paste your key here inside the quotes!
    LEONARDO_API_KEY: str = "00cc04d3-9d6d-484d-81e7-d025238300ed" 
    
    # ⚠️ MASTER SWITCHES
    # Set this to False to use the real API!
    USE_MOCK_VEO: bool = False       
    USE_MOCK_AUDIO: bool = False    

    # Storage Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOCAL_STORAGE: str = os.path.join(BASE_DIR, "..", "local_storage")

    class Config:
        case_sensitive = True

settings = Settings()