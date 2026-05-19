from google import genai
import json
import os

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

def encontrar_produto_similar(nome_produto, lista_existentes):

    prompt = f"""
    Você é um sistema de ERP.

    Compare o produto abaixo com a lista existente.

    Produto:
    {nome_produto}

    Lista:
    {lista_existentes}

    Se encontrar produto MUITO parecido,
    responda:

    {{
      "similar": true,
      "nome_existente": "NOME"
    }}

    Caso contrário:

    {{
      "similar": false
    }}

    Responda apenas JSON.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    texto = (
        response.text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    return json.loads(texto)