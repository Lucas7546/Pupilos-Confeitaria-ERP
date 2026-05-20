import mimetypes

def analisar_nota(caminho_imagem):
    # Detecta o tipo de arquivo automaticamente
    mime_type, _ = mimetypes.guess_type(caminho_imagem)
    if not mime_type:
        mime_type = "image/jpeg" # Fallback

    with open(caminho_imagem, "rb") as img:
        imagem_bytes = img.read()

    # O formato de chamada do SDK google-genai espera o conteúdo assim:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            """Analise esta nota fiscal ou comprovante de compra. 
            Extraia nome do produto, quantidade, valor unitário e valor total.
            Responda SOMENTE em formato JSON puro, sem explicações adicionais.""",
            {
                "mime_type": mime_type,
                "data": imagem_bytes
            }
        ]
    )
    return response.text