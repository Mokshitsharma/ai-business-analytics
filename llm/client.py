import os
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv


# Automatically finds .env anywhere in project
load_dotenv(find_dotenv())

# Wall-clock cap on a single LLM request. Keeps the report stage from
# hanging when the API key is invalid or the network is unavailable -
# the caller (LLMSummarizer) then falls back to a structured summary.
REQUEST_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))


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
            request_options={"timeout": REQUEST_TIMEOUT_SECONDS},
        )
        return response.text.strip()
