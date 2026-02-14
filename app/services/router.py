from google import genai
from google.genai import types
from app.core.config import settings
import logging

logger = logging.getLogger("Foundry.Router")

class DecisionEngine:
    def __init__(self):
        # Initialize client with a STRICT TIMEOUT to prevent long retries
        if settings.GOOGLE_API_KEY:
            self.client = genai.Client(
                api_key=settings.GOOGLE_API_KEY,
                http_options=types.HttpOptions(timeout=3000) # 1000ms = 1 Second Timeout
            )
        else:
            self.client = None

    def decide_provider(self, prompt: str) -> str:
        """
        Gemini analyzes the prompt and returns 'pexels' or 'leonardo'.
        """
        if not self.client:
            return "pexels"

        try:
            # 1. System Instruction
            system_instruction = """
            You are a Video Production Director. 
            Analyze the video prompt and return 'pexels' if it describes real-world, 
            generic footage (nature, business, cityscapes, people walking). 
            Return 'leonardo' if it requires sci-fi, fantasy, impossible AI visuals, 
            or specific artistic styles (cyberpunk, anime, oil painting).
            OUTPUT ONLY THE WORD 'pexels' OR 'leonardo'.
            """

            # 2. Call Gemini (Will fail in 1s if Rate Limited)
            response = self.client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.1
                )
            )
            
            decision = response.text.strip().lower()
            return "leonardo" if "leonardo" in decision else "pexels"

        except Exception as e:
            error_str = str(e).lower()
            
            # Catch Rate Limits AND Timeouts
            if "429" in error_str or "exhausted" in error_str or "timeout" in error_str or "deadline" in error_str:
                logger.warning(f"⚠️ Gemini Busy/Limit. Swapping to Pexels (Stock) immediately.")
            else:
                logger.error(f"❌ Decision Engine Error: {e}")
            
            # FAIL-SAFE: Always return pexels on error
            return "pexels" 

decision_engine = DecisionEngine()