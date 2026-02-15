from google import genai
from google.genai import types
from app.core.config import settings
import logging

logger = logging.getLogger("Foundry.Router")

class DecisionEngine:
    def __init__(self):
        if settings.GOOGLE_API_KEY:
            self.client = genai.Client(
                api_key=settings.GOOGLE_API_KEY
            )
        else:
            self.client = None

    def decide_provider(self, prompt: str) -> str:
        if not self.client:
            logger.warning("⚠️ GOOGLE_API_KEY missing. Defaulting to Pexels.")
            return "pexels"

        # --- UPDATED MODEL CASCADE ---
        # Based on your 'check_models.py' output.
        # 1. Try Gemini 2.5 Flash (Newest)
        # 2. Try Gemini 2.0 Flash Lite (Good backup, separate quota)
        # 3. Try Gemini 2.0 Flash (Original)
        candidate_models = [
            'gemini-2.5-flash',
            'gemini-2.0-flash-lite', 
            'gemini-2.0-flash'
        ]

        system_instruction = """
        Analyze the video prompt. 
        Return 'leonardo' if it requires sci-fi, fantasy, impossible AI visuals.
        Return 'pexels' for real-world, generic stock footage.
        """

        for model_name in candidate_models:
            try:
                response = self.client.models.generate_content(
                    model=model_name, 
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1
                    )
                )
                
                decision = response.text.strip().lower()
                
                if "leonardo" in decision:
                    logger.info(f"🤖 Gemini ({model_name}) Decided: LEONARDO (AI Video)")
                    return "leonardo"
                
                logger.info(f"🤖 Gemini ({model_name}) Decided: PEXELS (Stock Video)")
                return "pexels"

            except Exception as e:
                error_msg = str(e)
                # If Rate Limited (429) or Not Found (404), Log and Continue to next model
                if "429" in error_msg:
                    logger.warning(f"⚠️ Gemini {model_name} Busy (Rate Limit). Switching to next...")
                elif "404" in error_msg:
                    logger.warning(f"⚠️ Gemini {model_name} Not Found. Switching to next...")
                else:
                    logger.warning(f"⚠️ Gemini {model_name} Error: {e}")
                
                continue # Try the next model in the list

        # If ALL models fail, fallback to Pexels
        logger.error("❌ ALL Gemini Models failed. Fallback to Pexels.")
        return "pexels" 

decision_engine = DecisionEngine()