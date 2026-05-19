from google import genai
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def analisar_nota(caminho_imagem):

    with open(caminho_imagem, "rb") as img:
        imagem_bytes = img.read()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            """
            Analise esta nota fiscal brasileira.

            Extraia:
            - nome dos produtos
            - quantidade
            - valor unitário
            - valor total

            Responda SOMENTE em JSON válido.

            Exemplo:

            [
              {
                "produto": "Leite Condensado",
                "quantidade": 2,
                "valor_unitario": 7.50,
                "valor_total": 15.00
              }
            ]
            """,
            {
                "mime_type": "image/jpeg",
                "data": imagem_bytes
            }
        ]
    )

    return response.text