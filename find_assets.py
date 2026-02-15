from app.core.config import settings
import os

print("\n--- 🔍 FOUNDRY PATH DIAGNOSTICS ---")
print(f"1. BASE_DIR:      {settings.BASE_DIR}")
print(f"2. LOCAL_STORAGE: {settings.LOCAL_STORAGE}")
print(f"3. ASSETS_PATH:   {settings.ASSETS_PATH}")
print(f"4. WATERMARK:     {settings.WATERMARK_FILE}")

# Check if the folder exists
if settings.ASSETS_PATH.exists():
    print("✅ Assets folder EXISTS.")
    # List contents
    files = os.listdir(settings.ASSETS_PATH)
    print(f"📂 Folder Contents: {files}")
else:
    print("❌ Assets folder DOES NOT EXIST (It should have been created automatically).")

print("-----------------------------------\n")
