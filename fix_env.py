import os

# --- PASTE YOUR REAL KEYS BELOW ---
GOOGLE_KEY = "AIzaSyDdIJpdyGOF-CAuv_3-owW3fVzHwwl7q6M"  # Paste your Google Gemini Key here
PEXELS_KEY = "xGGjpVR1dr3nNhikyEslZb9qDVNrNsmKnAZnRrZyr0Pj19Y46ltnxC8k"  # Paste your Pexels Key here
LEONARDO_KEY = "00cc04d3-9d6d-484d-81e7-d025238300ed"   # Paste your Leonardo Key here

# --- DO NOT TOUCH BELOW THIS LINE ---
content = f"""GOOGLE_API_KEY={GOOGLE_KEY}
PEXELS_API_KEY={PEXELS_KEY}
LEONARDO_API_KEY={LEONARDO_KEY}
VIDEO_PROVIDER=auto
USE_MOCK_AUDIO=False
"""

with open(".env", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ .env file fixed! Now run 'python main.py'")