import json
import mimetypes
from modules.tenant_db import db_conn
from ape.services.ai_client import client
from difflib import SequenceMatcher
from utils.logger import log_info, log_erro
from flask_login import current_user
 
 
# Prompt detalhado — quanto mais específico, mais consistente o JSON retornado
_PROMPT_NOTA = """Você é um sistema especializado em leitura de notas fiscais brasileiras.
 
Analise a imagem e extraia TODOS os itens de compra encontrados.
 
Retorne SOMENTE um array JSON válido, sem markdown, sem explicações, sem texto antes ou depois.
 
Formato obrigatório de cada item:
[
  {
    "nome": "Nome do produto exatamente como está na nota",
    "quantidade": 1.0,
    "valor_unitario": 0.00,
    "valor_total": 0.00,
    "unidade": "UN"
  }
]
 
Regras:
- quantidade e valores devem ser números (float), nunca strings
- Se não conseguir ler o valor unitário, divida valor_total por quantidade
- unidade pode ser: UN, KG, G, L, ML, CX, PCT, FD
- Se a nota tiver apenas valor total sem unitário, coloque o mesmo em valor_unitario
- NUNCA retorne null nos campos numéricos — use 0.0 como fallback
- Retorne [] se não encontrar nenhum item legível
"""
 
 
def analisar_nota(caminho_imagem: str) -> str | None:
    """
    Analisa uma imagem de nota fiscal com o Gemini.
    Retorna string JSON com lista de itens ou None em caso de falha.
    """
    try:
        mime_type, _ = mimetypes.guess_type(caminho_imagem)
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"
 
        with open(caminho_imagem, "rb") as img:
            imagem_bytes = img.read()
 
        if len(imagem_bytes) == 0:
            log_erro("Arquivo de imagem está vazio.")
            return None
 
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                _PROMPT_NOTA,
                {"mime_type": mime_type, "data": imagem_bytes},
            ],
        )
 
        texto = (response.text or "").strip()
        if not texto:
            log_erro("Gemini retornou resposta vazia para a nota fiscal.")
            return None
 
        log_info(f"OCR realizado: {caminho_imagem}")
        return texto
 
    except FileNotFoundError:
        log_erro(f"Arquivo não encontrado: {caminho_imagem}")
        return None
    except Exception as e:
        log_erro(f"Erro crítico no OCR com Gemini: {e}")
        return None
 
 
def limpar_e_parsear_json(texto: str) -> list[dict] | None:
    """
    Limpa a resposta do Gemini e converte para lista Python.
    Trata os casos mais comuns de resposta malformada.
    Retorna None se não conseguir parsear.
    """
    if not texto:
        return None
 
    # Remove blocos de markdown que o modelo às vezes inclui
    texto = (
        texto
        .replace("```json", "")
        .replace("```JSON", "")
        .replace("```", "")
        .strip()
    )
 
    # Se o modelo retornou um objeto em vez de lista, tenta extrair
    if texto.startswith("{"):
        try:
            obj = json.loads(texto)
            # Tenta encontrar uma lista dentro do objeto
            for v in obj.values():
                if isinstance(v, list):
                    texto = json.dumps(v)
                    break
            else:
                texto = f"[{texto}]"
        except json.JSONDecodeError:
            pass
 
    try:
        dados = json.loads(texto)
        if not isinstance(dados, list):
            log_erro(f"JSON retornado não é uma lista: {type(dados)}")
            return None
 
        # Normaliza cada item garantindo tipos corretos
        itens = []
        for item in dados:
            if not isinstance(item, dict):
                continue
            itens.append({
                "nome":          str(item.get("nome") or "").strip(),
                "quantidade":    _to_float(item.get("quantidade"), 1.0),
                "valor_unitario": _to_float(item.get("valor_unitario")),
                "valor_total":   _to_float(item.get("valor_total")),
                "unidade":       str(item.get("unidade") or "UN").strip().upper(),
            })
 
        # Filtra itens sem nome
        itens = [i for i in itens if i["nome"]]
        return itens
 
    except json.JSONDecodeError as e:
        log_erro(f"JSON inválido retornado pelo Gemini: {e} | Texto: {texto[:200]}")
        return None
 
 
def _to_float(valor, default: float = 0.0) -> float:
    """Converte qualquer valor para float com segurança."""
    if valor is None:
        return default
    try:
        return float(str(valor).replace(",", ".").replace("R$", "").strip())
    except (ValueError, TypeError):
        return default
    

def enriquecer_itens_nota(itens):

    try:

        id_empresa = current_user.id_empresa

        with db_conn() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id_materia_prima,
                        nome
                    FROM materia_prima
                    WHERE id_empresa = %s
                    """,
                    (id_empresa,)
                )

                materias = cur.fetchall()

        resultado = []

        for item in itens:

            nome = item.get(
                "nome",
                ""
            )

            melhor_id = None
            melhor_score = 0

            for id_m, nome_m in materias:

                score = SequenceMatcher(
                    None,
                    nome.lower(),
                    nome_m.lower()
                ).ratio()

                if score > melhor_score:

                    melhor_score = score
                    melhor_id = id_m

            resultado.append(
                {
                    **item,
                    "id_materia_prima": melhor_id,
                    "status": (
                        "existente"
                        if melhor_score > 0.65
                        else "novo"
                    ),
                    "similaridade": round(
                        melhor_score,
                        2
                    )
                }
            )

        return resultado

    except Exception as e:

        log_erro(
            f"Erro ao enriquecer itens OCR: {e}"
        )

        return itens