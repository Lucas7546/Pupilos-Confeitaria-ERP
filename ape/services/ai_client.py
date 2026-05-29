import os

from google import genai

from utils.logger import log_erro


api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if api_key:
    client = genai.Client(api_key=api_key)
else:
    log_erro("Chave de API do Gemini não configurada.")
    client = genai.Client()

models = client.models
