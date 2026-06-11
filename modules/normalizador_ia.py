import json
import os
from google import genai
from utils.logger import log_erro

# Inicialização do cliente com segurança
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    log_erro("Chave de API do Gemini não configurada.")
client = genai.Client(api_key=api_key)

def encontrar_produto_similar(nome_produto, lista_existentes):
    """
    Usa IA para verificar se um produto novo é similar a algum já existente no ERP.
    """
    prompt = f"""
    Você é um sistema de ERP. Compare o produto abaixo com a lista existente.
    
    Produto: {nome_produto}
    Lista: {lista_existentes}
    
    Se encontrar um produto MUITO parecido, responda estritamente neste formato JSON:
    {{"similar": true, "nome_existente": "NOME"}}
    
    Caso contrário, responda:
    {{"similar": false}}
    
    Responda apenas JSON. Sem explicações. Sem markdown.
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        # Limpeza do texto da resposta
        texto = response.text.replace("```json", "").replace("```", "").strip()
        
        return json.loads(texto)

    except json.JSONDecodeError as e:
        log_erro(f"Erro ao decodificar resposta JSON da IA para produto '{nome_produto}': {e}")
        return {"similar": False}
        
    except Exception as e:
        log_erro(f"Erro ao consultar similaridade de produto com IA: {e}")
        return {"similar": False}