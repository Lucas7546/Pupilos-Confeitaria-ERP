import json
from difflib import SequenceMatcher

import pandas as pd
from google import genai
from modules.db import get_conn
from utils.logger import log_info, log_erro
from modules import vendas

client = genai.Client()


# =========================================================
# UTILITÁRIOS
# =========================================================
def limpar_numero(valor) -> float:
    if not valor:
        return 0.0
    try:
        return float(str(valor).replace("R$", "").replace(".", "").replace(",", ".").strip())
    except (ValueError, TypeError):
        return 0.0


# =========================================================
# LEITURA DE ARQUIVO
# Bug corrigido: a função recebia um caminho (str) após o save
# temporário em app.py, mas tentava usar .filename (attr de FileStorage).
# Agora aceita tanto string quanto FileStorage.
# =========================================================
def ler_arquivo(arquivo) -> pd.DataFrame:
    # Se vier um objeto FileStorage do Flask, pega o nome e lê diretamente
    if hasattr(arquivo, "filename"):
        nome = arquivo.filename.lower()
        if nome.endswith(".csv"):
            df = pd.read_csv(arquivo)
        elif nome.endswith((".xlsx", ".xls")):
            df = pd.read_excel(arquivo)
        else:
            raise ValueError(f"Formato não suportado: {nome}")
    else:
        # Veio como caminho de string (após tempfile.save)
        caminho = str(arquivo).lower()
        if caminho.endswith(".csv"):
            df = pd.read_csv(arquivo)
        elif caminho.endswith((".xlsx", ".xls")):
            df = pd.read_excel(arquivo)
        else:
            raise ValueError(f"Formato não suportado: {arquivo}")

    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


# =========================================================
# INTERPRETAÇÃO COM IA
# =========================================================
def interpretar_relatorio_com_ia(df: pd.DataFrame) -> list[dict]:
    try:
        colunas_relevantes = [
            c
            for c in df.columns
            if any(
                k in c.lower()
                for k in ["produto", "item", "valor", "total", "pedido", "data",
                           "quantidade", "taxa", "repasse", "canal"]
            )
        ]
        if colunas_relevantes:
            df = df[colunas_relevantes]

        payload = json.dumps(
            {
                "colunas": list(df.columns),
                "amostra": df.fillna("").head(50).astype(str).to_dict("records"),
            },
            ensure_ascii=False,
        )

        prompt = f"""
Você é um sistema de análise de delivery.
Retorne SOMENTE JSON válido em formato de lista.
Campos: produto, quantidade, valor_unitario, valor_total, taxa, repasse, data, canal_delivery
Dados:
{payload}
"""
        resposta = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        texto = (resposta.text or "").replace("```json", "").replace("```", "").strip()
        dados = json.loads(texto)

        if isinstance(dados, dict):
            return dados.get("vendas", [dados])
        return dados if isinstance(dados, list) else [dados]
    except Exception as e:
        log_erro(f"Erro IA relatório: {e}")
        raise


# =========================================================
# NORMALIZAÇÃO
# =========================================================
def normalizar_vendas(dados: list[dict]) -> list[dict]:
    vendas = []
    for item in dados:
        nome = item.get("produto", "")
        id_produto = localizar_produto_erp(nome)
        vendas.append(
            {
                "id_produto": id_produto,
                "produto": nome,
                "quantidade": limpar_numero(item.get("quantidade")),
                "valor_unitario": limpar_numero(item.get("valor_unitario")),
                "valor_total": limpar_numero(item.get("valor_total")),
                "taxa": limpar_numero(item.get("taxa")),
                "repasse": limpar_numero(item.get("repasse")),
                "data": item.get("data", ""),
                "canal_delivery": item.get("canal_delivery", "delivery"),
            }
        )
    return vendas


# =========================================================
# SALVAR VENDAS DELIVERY
# =========================================================
def registrar_vendas_importadas(vendas_importadas):
    
    processadas = 0

    for venda in vendas_importadas:

        id_produto = venda.get("id_produto")

        if not id_produto:
            continue

        quantidade = int(venda.get("quantidade", 0))

        if quantidade <= 0:
            continue

        valor_total = float(
            venda.get("valor_total") or 0
        )

        sucesso = vendas.registrar_venda(
            id_produto=id_produto,
            quantidade=quantidade,
            valor_total=valor_total,
            usuario="IMPORTADOR_IA"
        )

        if sucesso:
            processadas += 1

    return processadas


# =========================================================
# FINANCEIRO DO RELATÓRIO
# =========================================================
def gerar_financeiro(vendas: list[dict]) -> dict:
    return {
        "faturamento": sum(float(v.get("valor_total") or 0) for v in vendas),
        "taxas": sum(float(v.get("taxa") or 0) for v in vendas),
        "repasse_liquido": sum(float(v.get("repasse") or 0) for v in vendas),
    }


# =========================================================
# ORQUESTRAÇÃO DO PIPELINE COMPLETO
# =========================================================
def processar_relatorio_delivery(arquivo):

    try:

        log_info(
            "Iniciando processamento de relatório delivery."
        )

        df = ler_arquivo(arquivo)

        dados = interpretar_relatorio_com_ia(df)

        vendas_normalizadas = normalizar_vendas(dados)

        quantidade_processadas = registrar_vendas_importadas(
            vendas_normalizadas
        )

        financeiro = gerar_financeiro(
            vendas_normalizadas
        )

        log_info(
            f"{quantidade_processadas} vendas importadas."
        )

        return {
            "sucesso": True,
            "quantidade_vendas": quantidade_processadas,
            "financeiro": financeiro
        }

    except Exception as e:

        log_erro(
            f"Erro pipeline delivery: {e}"
        )

        return {
            "sucesso": False,
            "erro": str(e)
        }


# =========================================================
# LOCALIZAÇÃO DE PRODUTO NO ERP (COM APRENDIZADO DE ALIASES)
# =========================================================
def localizar_produto_erp(nome_produto: str) -> int | None:
    if not nome_produto:
        return None

    nome_produto = nome_produto.lower().strip()

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Tenta alias direto primeiro
                cur.execute(
                    "SELECT id_produto FROM aliases_produtos WHERE LOWER(nome_delivery) = %s LIMIT 1",
                    (nome_produto,),
                )
                alias = cur.fetchone()
                if alias:
                    return alias[0]

                # Busca por similaridade
                cur.execute("SELECT id_produto, nome FROM produtos WHERE ativo = 1")
                produtos = cur.fetchall()

            melhor_id = None
            melhor_score = 0.0
            LIMIAR = 0.60

            for id_p, nome in produtos:
                if not nome:
                    continue
                score = SequenceMatcher(None, nome_produto, nome.lower()).ratio()
                if score > melhor_score:
                    melhor_score = score
                    melhor_id = id_p

            if melhor_id and melhor_score >= LIMIAR:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO aliases_produtos (nome_delivery, id_produto)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (nome_produto, melhor_id),
                    )
                conn.commit()
                log_info(f"Alias aprendido: '{nome_produto}' → ID {melhor_id} ({melhor_score:.2f})")
                return melhor_id

        log_erro(f"Produto não encontrado no ERP: '{nome_produto}'")
        return None
    except Exception as e:
        log_erro(f"Erro ao localizar produto no ERP: {e}")
        return None

