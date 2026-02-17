from google import genai
from google.genai import types
from app.core.config import settings
import logging

logger = logging.getLogger("Foundry.Router")

class DecisionEngine:
    def __init__(self):
        if settings.GOOGLE_API_KEY:
            self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        else:
            self.client = None

    def decide_provider(self, prompt: str) -> str:
        """
        1. DECISION ENGINE: Decides Pexels vs Leonardo
        """
        if not self.client:
            logger.warning("⚠️ GOOGLE_API_KEY missing. Defaulting to Pexels.")
            return "pexels"

        candidate_models = ['gemini-2.5-flash', 'gemini-2.0-flash-lite', 'gemini-2.0-flash']

        system_instruction = """
        Analyze the video prompt. 
        Return 'leonardo' if it requires sci-fi, fantasy, impossible AI visuals, or specific artistic styles.
        Return 'pexels' for real-world, generic stock footage (nature, crowds, cities).
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
                if "leonardo" in decision: return "leonardo"
                return "pexels"

            except Exception as e:
                logger.warning(f"⚠️ Gemini {model_name} Router Error: {e}")
                continue 

        return "pexels"

    def refine_for_leonardo(self, raw_prompt: str) -> str:
        """
        2. PROMPT ENGINEER: Rewrites user prompt for Leonardo Motion 2.0
        """
        if not self.client: return raw_prompt

        # YOUR CUSTOM SYSTEM PROMPT
        sys_instruction = """You are an expert Prompt Engineer for Leonardo AI's "Motion 2.0" Video Model. 
        Your task is to rewrite raw user ideas into professional, cinematic video prompts that avoid the model's weaknesses and exploit its strengths.

        ### MODEL KNOWLEDGE:
        1. STRENGTHS (USE THESE):
           - Fluid elements: Fire, smoke, water, lightning, electricity, magic auras, floating debris.
           - Camera Movement: "Cinematic tracking shot", "slow zoom in", "pan right", "dynamic camera angle".
           - Lighting: "Volumetric lighting", "god rays", "cinematic lighting", "glowing eyes".
           - Style: "8k resolution", "masterpiece", "highly detailed", "Unreal Engine 5 render".

        2. WEAKNESSES (AVOID THESE):
           - Complex body movement: Running legs, sword fighting, punching (the AI often glitches limbs).
           - Hands: Detailed hand movements.
           - Long scenes: The video is only 4-5 seconds. Focus on a single "Looping" or "Impact" moment.

        ### INSTRUCTIONS:
        - Transform the user's request into a single, comma-separated descriptive string.
        - If the user asks for "fighting" or "running", CHANGE IT to "dashing with aura", "impact frame", or "camera flying past".
        - ALWAYS include keywords for atmosphere: "floating particles", "depth of field", "motion blur".
        - Keep the prompt under 75 words.
        - OUTPUT ONLY THE RAW PROMPT TEXT. NO EXPLANATION."""

        candidate_models = ['gemini-2.5-flash', 'gemini-2.0-flash-lite']

        for model_name in candidate_models:
            try:
                response = self.client.models.generate_content(
                    model=model_name, 
                    contents=raw_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        temperature=0.7
                    )
                )
                refined = response.text.strip()
                logger.info(f"✨ Gemini Refined Prompt: {refined}")
                return refined

            except Exception as e:
                logger.warning(f"⚠️ Gemini Refiner Error: {e}")
                continue
        
        return raw_prompt

decision_engine = DecisionEngine()