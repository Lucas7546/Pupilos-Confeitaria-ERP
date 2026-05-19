import os
import json
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def extrair_itens(imagem_bytes):

    prompt = """
    Você é um sistema especialista em leitura de notas fiscais brasileiras.

    Analise a imagem enviada e extraia:

    - nome do produto
    - quantidade
    - valor unitário
    - valor total

    Retorne APENAS JSON válido.

    Exemplo:

    [
      {
        "produto": "Leite Condensado",
        "quantidade": 2,
        "valor_unitario": 7.50,
        "valor_total": 15.00
      }
    ]
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            {
                "mime_type": "image/jpeg",
                "data": imagem_bytes
            }
        ]
    )

    texto = response.text.strip()

    texto = texto.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(texto)
    except:
        return []

