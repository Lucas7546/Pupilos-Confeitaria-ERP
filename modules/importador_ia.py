import json
from difflib import SequenceMatcher
import pandas as pd
from google import genai

from modules.db import conectar
from modules.produtos import cadastrar_produto
from utils.logger import log_info, log_erro

client = genai.Client()

# =========================
# UTIL
# =========================

def limpar_numero(valor):
    if not valor:
        return 0.0

    try:
        return float(
            str(valor)
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
    except:
        return 0.0


# =========================
# LEITURA
# =========================

def ler_arquivo(arquivo):
    nome = arquivo.filename.lower()

    if nome.endswith(".csv"):
        df = pd.read_csv(arquivo)
    elif nome.endswith((".xlsx", ".xls")):
        df = pd.read_excel(arquivo)
    else:
        raise ValueError("Formato não suportado.")

    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


# =========================
# IA - INTERPRETAÇÃO
# =========================

def interpretar_relatorio_com_ia(df):
    try:
        colunas = [
            c for c in df.columns
            if any(k in c.lower() for k in [
                "produto", "item", "valor", "total",
                "pedido", "data", "quantidade",
                "taxa", "repasse", "canal"
            ])
        ]

        if colunas:
            df = df[colunas]

        payload = json.dumps({
            "colunas": list(df.columns),
            "amostra": df.fillna("").head(50).astype(str).to_dict("records")
        }, ensure_ascii=False)

        prompt = f"""
Você é um sistema de análise de delivery.

Retorne SOMENTE JSON válido em formato de lista.

Campos:
produto, quantidade, valor_unitario, valor_total, taxa, repasse, data, canal_delivery

Dados:
{payload}
"""

        resposta = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        texto = (resposta.text or "").replace("```json", "").replace("```", "").strip()

        dados = json.loads(texto)

        if isinstance(dados, dict):
            return dados.get("vendas", [dados])

        return dados if isinstance(dados, list) else [dados]

    except Exception as e:
        log_erro(f"Erro IA relatório: {e}")
        raise


# =========================
# NORMALIZAÇÃO
# =========================

def normalizar_vendas(dados):
    vendas = []

    for item in dados:
        nome = item.get("produto", "")

        id_produto = localizar_produto_erp(nome)

        vendas.append({
            "id_produto": id_produto,
            "produto": nome,
            "quantidade": limpar_numero(item.get("quantidade")),
            "valor_unitario": limpar_numero(item.get("valor_unitario")),
            "valor_total": limpar_numero(item.get("valor_total")),
            "taxa": limpar_numero(item.get("taxa")),
            "repasse": limpar_numero(item.get("repasse")),
            "data": item.get("data", ""),
            "canal_delivery": item.get("canal_delivery", "delivery")
        })

    return vendas


# =========================
# SALVAR
# =========================

def salvar_vendas(vendas):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:

                for v in vendas:
                    cursor.execute("""
                        INSERT INTO vendas_delivery (
                            id_produto, produto, quantidade,
                            valor_unitario, valor_total,
                            taxa, repasse, data_venda, canal_delivery
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        v["id_produto"],
                        v["produto"],
                        v["quantidade"],
                        v["valor_unitario"],
                        v["valor_total"],
                        v["taxa"],
                        v["repasse"],
                        v["data"],
                        v["canal_delivery"]
                    ))

                conn.commit()

    except Exception as e:
        log_erro(f"Erro salvar vendas: {e}")
        raise


# =========================
# FINANCEIRO (mais seguro)
# =========================

def gerar_financeiro(vendas):
    return {
        "faturamento": sum(float(v.get("valor_total", 0) or 0) for v in vendas),
        "taxas": sum(float(v.get("taxa", 0) or 0) for v in vendas),
        "repasse_liquido": sum(float(v.get("repasse", 0) or 0) for v in vendas)
    }



# =========================
# ORQUESTRAÇÃO
# =========================

def processar_relatorio_delivery(arquivo):
    try:
        log_info(f"Iniciando processamento: {arquivo.filename}")

        df = ler_arquivo(arquivo)
        dados = interpretar_relatorio_com_ia(df)
        vendas = normalizar_vendas(dados)
        salvar_vendas(vendas)
        financeiro = gerar_financeiro(vendas)

        log_info(f"Processo concluído: {len(vendas)} vendas")

        return {
            "sucesso": True,
            "quantidade_vendas": len(vendas),
            "financeiro": financeiro
        }

    except Exception as e:
        log_erro(f"Erro pipeline delivery: {e}")
        return {
            "sucesso": False,
            "erro": str(e)
        }
    
# =========================
# LOCALIZAÇÃO ERP (SEM MUDAR LÓGICA)
# =========================

def localizar_produto_erp(nome_produto):
    if not nome_produto:
        return None

    nome_produto = nome_produto.lower().strip()

    try:
        with conectar() as conn:
            with conn.cursor() as cursor:

                cursor.execute("""
                    SELECT id_produto
                    FROM aliases_produtos
                    WHERE LOWER(nome_delivery) = %s
                    LIMIT 1
                """, (nome_produto,))

                alias = cursor.fetchone()
                if alias:
                    return alias[0]

                cursor.execute("""
                    SELECT id_produto, nome
                    FROM produtos
                    WHERE ativo = 1
                """)

                produtos = cursor.fetchall()

                melhor_id = None
                melhor_score = 0.0

                for id_p, nome in produtos:

                    if not nome:
                        continue

                    score = SequenceMatcher(
                        None,
                        nome_produto,
                        nome.lower()
                    ).ratio()

                    if score > melhor_score:
                        melhor_score = score
                        melhor_id = id_p

                LIMIAR = 0.60

                if melhor_id and melhor_score >= LIMIAR:

                    cursor.execute("""
                        INSERT INTO aliases_produtos (nome_delivery, id_produto)
                        VALUES (%s,%s)
                        ON CONFLICT DO NOTHING
                    """, (nome_produto, melhor_id))

                    conn.commit()

                    log_info(f"Alias aprendido: {nome_produto} ({melhor_score:.2f})")

                    return melhor_id

                log_erro(f"Produto não encontrado: {nome_produto}")
                return None

    except Exception as e:
        log_erro(f"Erro localizar produto: {e}")
        return None


def interpretar_item_delivery(nome):
    """
    IA interpreta nome complexo de item delivery.
    Retorna estrutura padronizada de produto.
    """

    if not nome:
        return {
            "produto_base": "",
            "tamanho": "",
            "sabores": [],
            "adicionais": [],
            "observacoes": ""
        }

    try:
        prompt = f"""
Você é um especialista em delivery e ERP gastronômico.

Analise o item abaixo e extraia:

- produto_base
- tamanho
- sabores (lista)
- adicionais (lista)
- observacoes

Regras obrigatórias:
- Retorne SOMENTE JSON válido
- Não explique nada
- Não use markdown
- Sempre use listas para sabores e adicionais

ITEM:
{nome}
"""

        resposta = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        texto = (resposta.text or "").strip()

        # =========================
        # LIMPEZA SEGURA
        # =========================
        texto = (
            texto
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        dados = json.loads(texto)

        return {
            "produto_base": dados.get("produto_base", ""),
            "tamanho": dados.get("tamanho", ""),
            "sabores": dados.get("sabores", []) if isinstance(dados.get("sabores"), list) else [],
            "adicionais": dados.get("adicionais", []) if isinstance(dados.get("adicionais"), list) else [],
            "observacoes": dados.get("observacoes", "")
        }

    except Exception as e:
        log_erro(f"Erro IA item delivery ({nome}): {e}")

        return {
            "produto_base": nome,
            "tamanho": "",
            "sabores": [],
            "adicionais": [],
            "observacoes": ""
        }