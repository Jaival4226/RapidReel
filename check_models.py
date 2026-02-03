import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load your .env file
load_dotenv()
api_key = "AIzaSyCPL-_x20LWTriBU35UwoWgLdxzGKD1Mxc"

if not api_key:
    print("❌ Error: GEMINI_API_KEY not found in .env")
else:
    genai.configure(api_key=api_key)
    print("✅ Authenticated. Asking Google for available models...")
    print("------------------------------------------------xxx")
    try:
        # List all models your key can access
        for m in genai.list_models():
            # We only care about models that can generate content (chat/text)
            if 'generateContent' in m.supported_generation_methods:
                print(f"Model Name: {m.name}")
    except Exception as e:
        print(f"❌ Error listing models: {e}")