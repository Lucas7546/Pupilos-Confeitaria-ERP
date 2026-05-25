import mimetypes
from utils.logger import log_info, log_erro
from google import genai # Certifique-se de que o SDK está configurado

# O cliente deve ser inicializado fora da função para reutilização
# Substitua 'sua-api-key' ou configure a variável de ambiente
client = genai.Client(api_key="SUA_API_KEY")

def analisar_nota(caminho_imagem):
    """
    Analisa uma imagem de nota fiscal e retorna dados extraídos em JSON.
    """
    try:
        # Detecta o tipo de arquivo
        mime_type, _ = mimetypes.guess_type(caminho_imagem)
        if not mime_type:
            mime_type = "image/jpeg"

        # Leitura segura do arquivo
        with open(caminho_imagem, "rb") as img:
            imagem_bytes = img.read()

        prompt = """Analise esta nota fiscal ou comprovante de compra. 
        Extraia os itens: nome do produto, quantidade, valor unitário e valor total.
        Responda SOMENTE em formato JSON puro, sem explicações adicionais."""

        # Chamada à API
        response = client.models.generate_content(
            model="gemini-2.0-flash", # Ajustado para versão estável atual
            contents=[
                prompt,
                {
                    "mime_type": mime_type,
                    "data": imagem_bytes
                }
            ]
        )

        log_info(f"OCR realizado com sucesso para o arquivo: {caminho_imagem}")
        return response.text

    except FileNotFoundError:
        log_erro(f"Arquivo não encontrado: {caminho_imagem}")
        return None
    except Exception as e:
        log_erro(f"Erro crítico ao processar OCR com Gemini: {e}")
        return None