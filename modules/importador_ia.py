import json
from difflib import SequenceMatcher

import pandas as pd
from google import genai
from modules.tenant_db import db_conn
from utils.logger import log_info, log_erro
from modules import vendas
from modules.tenant import get_empresa_id
from modules.produtos import cadastrar_produto

client = genai.Client()


# =========================================================
# UTILITÁRIOS
# =========================================================
def limpar_numero(valor) -> float:
    try:
        if valor is None:
            return 0.0

        if isinstance(valor, (int, float)):
            return float(valor)

        texto = str(valor).strip()

        if not texto:
            return 0.0

        texto = (
            texto.replace("R$", "")
                 .replace(".", "")
                 .replace(",", ".")
                 .strip()
        )

        return float(texto)

    except Exception:
        return 0.0

# =========================================================
# LEITURA DE ARQUIVO
# =========================================================
def ler_arquivo(arquivo) -> pd.DataFrame:

    def carregar(nome, source):

        if nome.endswith(".csv"):
            return pd.read_csv(source, encoding="utf-8-sig")

        elif nome.endswith((".xlsx", ".xls")):
            return pd.read_excel(source)

        raise ValueError(f"Formato não suportado: {nome}")

    try:

        # Flask FileStorage
        if hasattr(arquivo, "filename"):

            nome = arquivo.filename.lower()
            arquivo.seek(0)
            df = carregar(nome, arquivo)

        else:

            caminho = str(arquivo)
            df = carregar(caminho.lower(), arquivo)

        df.columns = [str(c).strip().lower() for c in df.columns]

        return df

    except Exception as e:
        raise ValueError(f"Erro ao ler arquivo: {e}")

# =========================================================
# INTERPRETAÇÃO COM IA
# =========================================================
def interpretar_relatorio_com_ia(df: pd.DataFrame) -> list[dict]:
    try:
        colunas_relevantes = [
            c for c in df.columns
            if any(
                k in c.lower()
                for k in [
                    "produto", "item", "valor", "total", "pedido",
                    "data", "quantidade", "taxa", "repasse", "canal"
                ]
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

REGRAS OBRIGATÓRIAS:
- Responda SOMENTE JSON válido
- Nunca inclua texto fora do JSON
- Sempre retorne uma LISTA de objetos

Campos permitidos:
produto, quantidade, valor_unitario, valor_total, taxa, repasse, data, canal_delivery

Dados:
{payload}
"""

        resposta = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        texto = (resposta.text or "").strip()

        # remove lixo de markdown
        texto = texto.replace("```json", "").replace("```", "").strip()

        try:
            dados = json.loads(texto)
        except json.JSONDecodeError:
            log_erro(f"IA retornou JSON inválido: {texto[:300]}")
            return []

        if isinstance(dados, dict):
            return dados.get("vendas", [])

        if isinstance(dados, list):
            return dados

        return []

    except Exception as e:
        log_erro(f"Erro IA relatório: {e}")
        return []


# =========================================================
# NORMALIZAÇÃO
# =========================================================
def normalizar_vendas(dados: list[dict]) -> list[dict]:
    vendas = []

    for item in dados:
        try:
            nome = (item.get("produto") or "").strip()

            if not nome:
                continue

            # evita custo pesado desnecessário
            id_produto = garantir_produto_erp(
                nome,
                limpar_numero(item.get("valor_unitario"))
            )

            venda = {
                "id_produto": id_produto,
                "produto": nome,
                "quantidade": limpar_numero(item.get("quantidade")),
                "valor_unitario": limpar_numero(item.get("valor_unitario")),
                "valor_total": limpar_numero(item.get("valor_total")),
                "taxa": limpar_numero(item.get("taxa")),
                "repasse": limpar_numero(item.get("repasse")),
                "data": item.get("data") or None,
                "canal_delivery": item.get("canal_delivery") or "delivery",
            }

            vendas.append(venda)

        except Exception as e:
            log_erro(f"Erro ao normalizar venda: {e} | item={item}")

    return vendas


# =========================================================
# SALVAR VENDAS DELIVERY
# =========================================================
def registrar_vendas_importadas(vendas_importadas):
    processadas = 0
    erros = 0

    for venda in vendas_importadas:
        try:
            id_produto = venda.get("id_produto")

            if not id_produto:
                continue

            quantidade = int(venda.get("quantidade") or 0)
            if quantidade <= 0:
                continue

            valor_total = float(venda.get("valor_total") or 0)

            sucesso = vendas.registrar_venda(
                id_produto=id_produto,
                quantidade=quantidade,
                valor_total=valor_total,
                usuario="IMPORTADOR_IA"
            )

            if sucesso:
                processadas += 1
            else:
                erros += 1

        except Exception as e:
            erros += 1
            log_erro(
                f"Erro ao registrar venda importada (produto {venda.get('id_produto')}): {e}"
            )

    log_info(
        f"Importação finalizada. Processadas: {processadas} | Erros: {erros}"
    )

    return processadas


# =========================================================
# FINANCEIRO DO RELATÓRIO
# =========================================================
def gerar_financeiro(vendas: list[dict]) -> dict:

    def safe_float(value) -> float:
        try:
            if value is None:
                return 0.0
            return float(str(value).replace("R$", "").replace(".", "").replace(",", ".").strip())
        except (ValueError, TypeError):
            return 0.0

    faturamento = 0.0
    taxas = 0.0
    repasse = 0.0

    for v in vendas:

        faturamento += safe_float(v.get("valor_total"))
        taxas += safe_float(v.get("taxa"))
        repasse += safe_float(v.get("repasse"))

    return {
        "faturamento": round(faturamento, 2),
        "taxas": round(taxas, 2),
        "repasse_liquido": round(repasse, 2),
    }


# =========================================================
# ORQUESTRAÇÃO DO PIPELINE COMPLETO
# =========================================================
def processar_relatorio_delivery_commit(vendas_norm):

    try:
        processadas = 0
        erros = 0

        for v in vendas_norm:

            try:
                id_produto = v.get("id_produto")

                if not id_produto:
                    continue

                qtd = int(float(v.get("quantidade") or 0))

                if qtd <= 0:
                    continue

                sucesso = vendas.registrar_venda(
                    id_produto=id_produto,
                    quantidade=qtd,
                    valor_total=float(v.get("valor_total") or 0),
                    usuario="IMPORTADOR_IA"
                )

                if sucesso:
                    processadas += 1
                else:
                    erros += 1

            except Exception as e:
                erros += 1
                log_erro(
                    f"Erro ao processar item importado (produto {v.get('id_produto')}): {e}"
                )

        return {
            "sucesso": True,
            "processadas": processadas,
            "erros": erros
        }

    except Exception as e:
        log_erro(f"Erro commit delivery: {e}")

        return {
            "sucesso": False,
            "erro": str(e),
            "processadas": 0
        }


# =========================================================
# LOCALIZAÇÃO DE PRODUTO NO ERP (COM APRENDIZADO DE ALIASES)
# =========================================================
def localizar_produto_erp(nome_produto: str) -> int | None:

    if not nome_produto:
        return None

    nome_produto = str(nome_produto).strip().lower()

    if not nome_produto:
        return None

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return None

        with db_conn() as conn:
            with conn.cursor() as cur:

                # 1. tenta alias direto
                cur.execute("""
                    SELECT id_produto
                    FROM aliases_produtos
                    WHERE LOWER(nome_delivery) = %s
                    LIMIT 1
                """, (nome_produto,))

                alias = cur.fetchone()
                if alias:
                    return alias[0]

                # 2. busca produtos da empresa
                cur.execute("""
                    SELECT id_produto, nome
                    FROM produtos
                    WHERE ativo = 1
                    AND id_empresa = %s
                """, (id_empresa,))

                produtos = cur.fetchall()

                melhor_id = None
                melhor_score = 0.0
                LIMIAR = 0.65

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

                # 3. só salva alias se confiança for boa
                if melhor_id and melhor_score >= LIMIAR:

                    cur.execute("""
                        INSERT INTO aliases_produtos
                        (nome_delivery, id_produto)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (nome_produto, melhor_id))

                return melhor_id

        return None

    except Exception as e:
        log_erro(f"Erro ao localizar produto ERP: {e}")
        return None


def garantir_produto_erp(nome: str, preco_sugerido=0.0):
    if not nome:
        return None

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return None

        nome_limpo = nome.strip()

        with db_conn() as conn:
            with conn.cursor() as cur:

                # 1. tenta achar existente
                cur.execute("""
                    SELECT id_produto
                    FROM produtos
                    WHERE LOWER(nome) = LOWER(%s)
                    AND id_empresa = %s
                    LIMIT 1
                """, (nome_limpo, id_empresa))

                row = cur.fetchone()

                if row:
                    return row[0]

                # 2. cria produto corretamente
                cur.execute("""
                    INSERT INTO produtos
                    (
                        id_empresa,
                        nome,
                        preco_venda,
                        categoria,
                        ativo
                    )
                    VALUES
                    (%s, %s, %s, %s, %s)
                    RETURNING id_produto
                """, (
                    id_empresa,
                    nome_limpo,
                    float(preco_sugerido or 0),
                    "IMPORTADO",
                    1
                ))

                id_produto = cur.fetchone()[0]

        log_info(
            f"Produto criado automaticamente pelo importador: {nome_limpo}"
        )

        return id_produto

    except Exception as e:
        log_erro(f"Erro ao garantir produto ERP '{nome}': {e}")
        return None


def processar_relatorio_delivery_preview(arquivo):

    try:
        from modules.tenant import get_empresa_id

        id_empresa = get_empresa_id()
        if not id_empresa:
            return {"sucesso": False, "erro": "Empresa não definida"}

        df = ler_arquivo(arquivo)

        dados = interpretar_relatorio_com_ia(df)
        vendas_norm = normalizar_vendas(dados)

        financeiro = gerar_financeiro(vendas_norm)

        produtos_preview = []

        for v in vendas_norm:

            nome = v.get("produto", "")

            produtos_preview.append(
                {
                    "nome": nome,
                    "quantidade": v.get("quantidade", 0),
                    "valor_unitario": v.get("valor_unitario", 0),
                    "status": "novo" if not v.get("id_produto") else "existente",
                }
            )

        return {
            "sucesso": True,
            "resumo": {
                "total_itens": len(vendas_norm),
                "faturamento": financeiro.get("faturamento", 0),
                "taxas": financeiro.get("taxas", 0),
                "repasse": financeiro.get("repasse_liquido", 0),
            },
            "vendas": vendas_norm,
            "produtos": produtos_preview,
        }

    except Exception as e:
        log_erro(f"Erro preview delivery: {e}")
        return {"sucesso": False, "erro": str(e)}
    


def processar_relatorio_delivery_commit(vendas_norm):

    try:
        from modules.tenant import get_empresa_id

        id_empresa = get_empresa_id()
        if not id_empresa:
            return {"sucesso": False, "erro": "Empresa não definida"}

        processadas = 0

        for v in vendas_norm:

            try:

                if not v.get("id_produto"):
                    continue

                qtd = int(v.get("quantidade") or 0)

                if qtd <= 0:
                    continue

                sucesso = vendas.registrar_venda(
                    id_produto=v["id_produto"],
                    quantidade=qtd,
                    valor_total=float(v.get("valor_total") or 0),
                    usuario="IMPORTADOR_IA",
                )

                if sucesso:
                    processadas += 1

            except Exception as e:
                log_erro(
                    f"Erro ao processar item importado (prod {v.get('id_produto')}): {e}"
                )

        return {
            "sucesso": True,
            "processadas": processadas,
        }

    except Exception as e:
        log_erro(f"Erro commit delivery: {e}")
        return {"sucesso": False, "erro": str(e)}