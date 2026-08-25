import os
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv


# ✅ Automatically finds .env anywhere in project
load_dotenv(find_dotenv())


class LLMClient:
    def __init__(self, model: Optional[str] = None):
        api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError("GOOGLE_API_KEY NOT FOUND")

        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel(
            model or "gemini-flash-latest"
        )

    def generate(self, prompt: str) -> str:
        response = self.model.generate_content(
            prompt,
            generation_config={"temperature": 0.3},
        )
        return response.text.strip()