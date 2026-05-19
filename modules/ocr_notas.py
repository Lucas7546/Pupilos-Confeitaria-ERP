import easyocr
import re

reader = easyocr.Reader(['pt'])

# =========================================================
# LER NOTA FISCAL
# =========================================================
def ler_nota(caminho_imagem):

    resultados = reader.readtext(caminho_imagem, detail=0)

    texto = "\n".join(resultados)

    return texto


# =========================================================
# EXTRAIR ITENS DA NOTA
# =========================================================
def extrair_itens(texto):

    itens = []

    linhas = texto.split("\n")

    for linha in linhas:

        linha = linha.strip()

        # Exemplo:
        # LEITE INTEGRAL 2 12,99

        match = re.search(
            r"([A-Za-zÀ-ÿ\s]+)\s+(\d+)\s+([\d,]+)",
            linha
        )

        if match:

            nome = match.group(1).strip()
            quantidade = int(match.group(2))
            valor = float(match.group(3).replace(",", "."))

            itens.append({
                "nome": nome,
                "quantidade": quantidade,
                "valor": valor
            })

    return itens