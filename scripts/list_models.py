# scripts/list_models.py

import google.generativeai as genai
from auditmind.config import settings

genai.configure(api_key=settings.gemini_api_key)

for model in genai.list_models():
    if "generateContent" in model.supported_generation_methods:
        print(model.name)