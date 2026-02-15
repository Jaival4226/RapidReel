import os
from google import genai
from dotenv import load_dotenv

# Load your API key from the .env file
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ Error: GOOGLE_API_KEY not found in .env file.")
    exit()

print(f"🔑 Checking permissions for Key ending in: ...{api_key[-5:]}")

try:
    # Connect to Google
    client = genai.Client(api_key=api_key)
    
    print("\n--- 📋 AVAILABLE MODELS FOR YOU ---")
    found_any = False

    # List every model your key can access
    for model in client.models.list():
        # We only care about models that can generate text/video content
        if "generateContent" in model.supported_actions:
            print(f"✅ {model.name}")
            found_any = True
            
    if not found_any:
        print("⚠️ No content generation models found. Your key might be restricted.")
    
    print("-----------------------------------\n")

except Exception as e:
    print(f"\n❌ CONNECTION ERROR: {e}")
    print("This usually means the API Key is invalid or has no Generative AI enabled.")