from dotenv import load_dotenv
load_dotenv()

import os
import google.generativeai as genai

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

print("=== ALL AVAILABLE MODELS ===\n")
for m in genai.list_models():
    methods = getattr(m, 'supported_generation_methods', [])
    print(f"{m.name}  →  {methods}")