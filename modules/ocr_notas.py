import mimetypes

from google import genai

from utils.logger import log_info, log_erro

# Bug corrigido: API key não deve ser hardcoded — vazaria em repositório.
# O Client() sem argumentos usa automaticamente a variável de ambiente
# GOOGLE_API_KEY (ou GEMINI_API_KEY, dependendo da versão do SDK).
# Configure no Render em Settings → Environment Variables.
client = genai.Client()


def analisar_nota(caminho_imagem: str) -> str | None:
    """
    Analisa uma imagem de nota fiscal com o Gemini e retorna JSON
    com os itens encontrados (nome, quantidade, valor unitário, total).
    """
    try:
        mime_type, _ = mimetypes.guess_type(caminho_imagem)
        if not mime_type:
            mime_type = "image/jpeg"

        with open(caminho_imagem, "rb") as img:
            imagem_bytes = img.read()

        prompt = (
            "Analise esta nota fiscal ou comprovante de compra. "
            "Extraia os itens: nome do produto, quantidade, valor unitário e valor total. "
            "Responda SOMENTE em formato JSON puro, sem explicações adicionais."
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, {"mime_type": mime_type, "data": imagem_bytes}],
        )

        log_info(f"OCR realizado com sucesso: {caminho_imagem}")
        return response.text

    except FileNotFoundError:
        log_erro(f"Arquivo não encontrado: {caminho_imagem}")
        return None
    except Exception as e:
        log_erro(f"Erro crítico no OCR com Gemini: {e}")
        return None
