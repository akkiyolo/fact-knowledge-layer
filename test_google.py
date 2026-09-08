import os
from app.config import get_settings
import google.generativeai as genai

settings = get_settings()
genai.configure(api_key=settings.google_api_key)

try:
    model = genai.GenerativeModel("gemini-3.5-flash")
    response = model.generate_content("Hello")
    print(f"Success for gemini-3.5-flash: {response.text.strip()}")
except Exception as e:
    print(f"Failed for gemini-3.5-flash: {e}")
