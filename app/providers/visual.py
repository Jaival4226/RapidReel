import requests
import time
import os
import shutil
from pathlib import Path
from app.core.config import settings

def generate_video(prompt: str, output_filename: str) -> str:
    """
    Generates a video using Leonardo.ai's API.
    Target Model: Seedance 1.0 Pro Fast (mapped to 'SEEDANCE1_LITE' in Leonardo)
    """
    
    # ---------------------------------------------------------
    # 1. MOCK MODE CHECK
    # ---------------------------------------------------------
    if settings.USE_MOCK_VEO:
        print(f"🎭 Mock Mode: Simulating generation for '{prompt}'...")
        time.sleep(2)
        mock_path = Path(settings.LOCAL_STORAGE) / "outputs"
        mock_path.mkdir(parents=True, exist_ok=True)
        return str(mock_path / "placeholder.mp4")

    # ---------------------------------------------------------
    # 2. PREPARE THE API REQUEST
    # ---------------------------------------------------------
    print(f"🚀 Sending prompt to Leonardo (Seedance 1.0 Pro Fast)...")
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {settings.LEONARDO_API_KEY}"
    }

    url_generate = "https://cloud.leonardo.ai/api/rest/v1/generations-text-to-video"
    
    payload = {
        "prompt": prompt,
        
        # ⚡️ CRITICAL: Leonardo maps "Pro Fast" to "SEEDANCE1_LITE"
        "modelId": "SEEDANCE1_LITE", 
        
        "duration": 5,           # Fast model supports 5s or 10s
        "isPublic": False,
        "height": 576,           # Best for speed
        "width": 1024
    }

    # ---------------------------------------------------------
    # 3. START THE JOB
    # ---------------------------------------------------------
    try:
        response = requests.post(url_generate, json=payload, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Leonardo Error: {response.text}")
            return None
            
        data = response.json()
        # Handle different response structures
        generation_id = data.get('generationId') or data.get('sdGenerationJob', {}).get('generationId')
        
        if not generation_id:
             print(f"❌ Failed to get Generation ID. Response: {data}")
             return None
             
        print(f"⏳ Job started! ID: {generation_id}")

    except Exception as e:
        print(f"❌ Failed to connect to Leonardo: {e}")
        return None

    # ---------------------------------------------------------
    # 4. POLL UNTIL COMPLETE
    # ---------------------------------------------------------
    url_get = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
    
    # Wait up to 2 minutes (24 checks * 5 seconds)
    # The Fast model usually finishes in 20-40 seconds.
    for i in range(24):
        time.sleep(5) 
        
        try:
            check_response = requests.get(url_get, headers=headers)
            if check_response.status_code == 200:
                data = check_response.json()
                gen_data = data.get('generations_by_pk')
                
                if not gen_data: continue
                
                status = gen_data.get('status')
                
                if status == "COMPLETE":
                    print("✅ Generation Complete! Finding video URL...")
                    generated_items = gen_data.get('generated_images', [])
                    
                    # Try to find the URL in known fields
                    video_url = None
                    if generated_items:
                        video_url = generated_items[0].get('motionMP4URL') or generated_items[0].get('url')
                    
                    if video_url:
                        print(f"⬇️ Downloading video...")
                        return download_file(video_url, output_filename)
                    else:
                        print("❌ Job Complete but URL missing (Leonardo API quirk).")
                        return None
            
                elif status == "FAILED":
                    print("❌ Generation Failed on Leonardo's side.")
                    return None
                
                print(f"   ... Status: {status} (Wait {i+1}/24)")
                
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            
    print("❌ Timed out.")
    return None

def download_file(url: str, local_filename: str) -> str:
    try:
        output_path = Path(local_filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"💾 Saved to: {local_filename}")
        return str(local_filename)
    except Exception as e:
        print(f"❌ Failed to download: {e}")
        return None