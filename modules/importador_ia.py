from datetime import datetime
import pandas as pd
import json
from difflib import SequenceMatcher
from google import genai
from modules.db import conectar
from modules.produtos import cadastrar_produto


client = genai.Client()


def limpar_numero(valor):

    if valor is None:
        return 0

    valor = str(valor)

    valor = (
        valor
        .replace("R$", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )

    try:
        return float(valor)

    except:
        return 0


def ler_arquivo(arquivo):
    """
    Lê CSV ou Excel automaticamente.
    """

    nome = arquivo.filename.lower()

    if nome.endswith(".csv"):

        df = pd.read_csv(arquivo)

    elif nome.endswith(".xlsx") or nome.endswith(".xls"):

        df = pd.read_excel(arquivo)

    else:

        raise Exception("Formato de arquivo não suportado.")

    # normaliza nomes colunas
    df.columns = [
        str(col).strip().lower()
        for col in df.columns
    ]

    return df



def interpretar_relatorio_com_ia(df):
    """
    Usa IA para interpretar qualquer relatório de delivery.
    """

    # =========================
    # FILTRAR COLUNAS RELEVANTES
    # =========================

    colunas_permitidas = []

    for coluna in df.columns:

        nome = coluna.lower()

        if any(x in nome for x in [
            "produto",
            "item",
            "valor",
            "total",
            "pedido",
            "data",
            "quantidade",
            "taxa",
            "repasse",
            "canal"
        ]):

            colunas_permitidas.append(coluna)

    if colunas_permitidas:
        df = df[colunas_permitidas]

    # =========================
    # PEGAR AMOSTRA SEGURA
    # =========================

    amostra = (
        df
        .fillna("")
        .head(50)
        .astype(str)
        .to_dict(orient="records")
    )

    colunas = list(df.columns)

    texto = json.dumps({
        "colunas": colunas,
        "amostra": amostra
    }, ensure_ascii=False)

    # =========================
    # PROMPT IA
    # =========================

    prompt = f"""
    Você é um sistema especialista em relatórios de delivery.

    Analise o JSON abaixo e descubra automaticamente:

    - produto
    - quantidade
    - valor_unitario
    - valor_total
    - taxa
    - repasse
    - data
    - canal_delivery

    IMPORTANTE:

    - O relatório pode ser do iFood, Keeta, 99Food ou qualquer delivery.
    - Os nomes das colunas podem variar.
    - Você deve identificar automaticamente os significados.
    - Ignore colunas irrelevantes.
    - Retorne SOMENTE JSON válido.
    - Nunca explique nada.
    - Nunca use markdown.
    - O retorno deve ser uma LISTA JSON.

    JSON DO RELATÓRIO:

    {texto}
    """

    resposta = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    texto_resposta = resposta.text.strip()

    texto_resposta = (
        texto_resposta
        .replace("```json", "")
        .replace("```", "")
        .replace("\n", " ")
        .strip()
    )

    try:

        dados = json.loads(texto_resposta)

    except Exception as e:

        print("ERRO IA:")
        print(texto_resposta)

        raise Exception(
            f"IA retornou JSON inválido: {e}"
        )

    # =========================
    # NORMALIZA JSON
    # =========================

    if isinstance(dados, dict):

        if "vendas" in dados:
            dados = dados["vendas"]

        else:
            dados = [dados]

    return dados


def normalizar_vendas(dados):

    vendas = []

    for item in dados:

        nome_produto = item.get("produto", "")

        id_produto = localizar_produto_erp(
            nome_produto
        )

        vendas.append({

            "id_produto":
                id_produto,

            "produto":
                nome_produto,

            "quantidade":
                limpar_numero(item.get("quantidade")),

            "valor_unitario":
                limpar_numero(item.get("valor_unitario")),

            "valor_total":
                limpar_numero(item.get("valor_total")),

            "taxa":
                limpar_numero(item.get("taxa")),

            "repasse":
                limpar_numero(item.get("repasse")),

            "data":
                item.get("data", ""),

            "canal_delivery":
                item.get("canal_delivery", "delivery")

        })

    return vendas


def salvar_vendas(vendas):
    """
    Salva vendas importadas no PostgreSQL.
    """

    conn = conectar()

    try:

        cursor = conn.cursor()

        for venda in vendas:

            cursor.execute("""

                INSERT INTO vendas_delivery (

                    id_produto,

                    produto,

                    quantidade,

                    valor_unitario,

                    valor_total,

                    taxa,

                    repasse,

                    data_venda,

                    canal_delivery

                )

                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)

            """, (

                venda["id_produto"],

                venda["produto"],

                venda["quantidade"],

                venda["valor_unitario"],

                venda["valor_total"],

                venda["taxa"],

                venda["repasse"],

                venda["data"],

                venda["canal_delivery"]

            ))

        conn.commit()

    except Exception as e:

        conn.rollback()

        print(f"Erro ao salvar vendas: {e}")

        raise e

    finally:

        conn.close()


def gerar_financeiro(vendas):
    """
    Gera resumo financeiro do relatório.
    """

    total_vendas = sum(
        v["valor_total"]
        for v in vendas
    )

    total_taxas = sum(
        v["taxa"]
        for v in vendas
    )

    total_repasse = sum(
        v["repasse"]
        for v in vendas
    )

    return {

        "faturamento":
            total_vendas,

        "taxas":
            total_taxas,

        "repasse_liquido":
            total_repasse

    }

def processar_relatorio_delivery(arquivo):

    try:

        # =========================
        # LER
        # =========================

        df = ler_arquivo(arquivo)

        # =========================
        # IA
        # =========================

        dados_ia = interpretar_relatorio_com_ia(df)

        # =========================
        # NORMALIZAR
        # =========================

        vendas = normalizar_vendas(dados_ia)

        # =========================
        # SALVAR
        # =========================

        salvar_vendas(vendas)

        # =========================
        # FINANCEIRO
        # =========================

        financeiro = gerar_financeiro(vendas)

        return {

            "sucesso": True,

            "quantidade_vendas":
                len(vendas),

            "financeiro":
                financeiro

        }

    except Exception as e:

        print(f"ERRO IMPORTADOR IA: {e}")

        return {

            "sucesso": False,

            "erro": str(e)

        }

def localizar_produto_erp(nome_produto):

    conn = conectar()

    try:

        cursor = conn.cursor()

        nome_produto = (
            nome_produto
            .lower()
            .strip()
        )

        # =====================================
        # 1. PROCURA ALIAS JÁ APRENDIDO
        # =====================================

        cursor.execute("""

            SELECT
                id_produto

            FROM aliases_produtos

            WHERE LOWER(nome_delivery) = %s

        """, (nome_produto,))

        alias = cursor.fetchone()

        if alias:
            return alias[0]

        # =====================================
        # 2. PROCURA PRODUTOS ERP
        # =====================================

        cursor.execute("""

            SELECT
                id_produto,
                nome

            FROM produtos

            WHERE ativo = 1

        """)

        produtos = cursor.fetchall()

        melhor_id = None
        melhor_nome = None
        melhor_score = 0

        for produto in produtos:

            id_produto = produto[0]
            nome_erp = produto[1]

            similaridade = SequenceMatcher(

                None,

                nome_produto,

                nome_erp.lower()

            ).ratio()

            if similaridade > melhor_score:

                melhor_score = similaridade
                melhor_id = id_produto
                melhor_nome = nome_erp

        # =====================================
        # 3. APRENDE AUTOMATICAMENTE
        # =====================================

        if melhor_score >= 0.60:

            cursor.execute("""

                INSERT INTO aliases_produtos (

                    nome_delivery,
                    id_produto

                )

                VALUES (%s,%s)

                ON CONFLICT (nome_delivery)
                DO NOTHING

            """, (

                nome_produto,
                melhor_id

            ))

            conn.commit()

            print(f"""
IA APRENDEU:
{nome_produto}
=
{melhor_nome}
""")

            return melhor_id

        # =====================================
        # 4. NÃO ENCONTROU → CRIA AUTOMÁTICO
        # =====================================

        print(f"""
PRODUTO NOVO DETECTADO:
{nome_produto}
""")

        cadastrar_produto(

            nome=nome_produto.title(),

            preco_venda=0,

            categoria="Delivery"

        )

        # =====================================
        # BUSCA O NOVO ID
        # =====================================

        cursor.execute("""

            SELECT id_produto

            FROM produtos

            WHERE LOWER(nome) = %s

            LIMIT 1

        """, (nome_produto,))

        novo = cursor.fetchone()

        if novo:

            novo_id = novo[0]

            cursor.execute("""

                INSERT INTO aliases_produtos (

                    nome_delivery,
                    id_produto

                )

                VALUES (%s,%s)

                ON CONFLICT (nome_delivery)
                DO NOTHING

            """, (

                nome_produto,
                novo_id

            ))

            conn.commit()

            print(f"""
PRODUTO CRIADO AUTOMATICAMENTE:
{nome_produto}
""")

            return novo_id

        return None

    finally:

        conn.close()


def interpretar_item_delivery(nome):
    """
    IA interpreta nome complexo de item delivery.
    """

    prompt = f"""
    Você é um especialista em delivery e ERP gastronômico.

    Analise o item abaixo.

    Descubra:

    - produto_base
    - tamanho
    - sabores
    - adicionais
    - observacoes

    IMPORTANTE:
    - Retorne SOMENTE JSON válido
    - Nunca explique
    - Nunca use markdown
    - sabores e adicionais devem ser LISTAS

    ITEM:

    {nome}
    """

    resposta = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    texto = (
        resposta.text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:

        dados = json.loads(texto)

        return {

            "produto_base":
                dados.get("produto_base", ""),

            "tamanho":
                dados.get("tamanho", ""),

            "sabores":
                dados.get("sabores", []),

            "adicionais":
                dados.get("adicionais", []),

            "observacoes":
                dados.get("observacoes", "")

        }

    except Exception as e:

        print("ERRO IA ITEM DELIVERY:")
        print(texto)

        return {

            "produto_base": nome,
            "tamanho": "",
            "sabores": [],
            "adicionais": [],
            "observacoes": ""

        }
