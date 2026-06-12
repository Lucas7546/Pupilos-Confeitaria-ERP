from datetime import datetime, timedelta
from modules.receitas import calcular_custo_receita
from modules.tenant_db import db_conn
from modules.tenant import get_empresa_id
from flask_login import current_user
from utils.logger import log_info, log_erro
from modules.estoque import obter_saldo_subproduto, obter_saldo_materia_prima, obter_saldo_produto


# =========================================================
# RESUMO PARA O DASHBOARD
# =========================================================
def obter_resumo_periodo(dias: int = 7) -> dict:
    try:

        from modules.tenant import get_empresa_id

        data_inicio = datetime.now() - timedelta(days=dias)
        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        COALESCE(SUM(valor_total), 0),
                        COUNT(id_venda),
                        COALESCE(SUM(lucro), 0)
                    FROM vendas
                    WHERE data_venda >= %s
                    AND id_empresa = %s
                """, (data_inicio, id_empresa))

                faturamento, total_vendas, lucro = cur.fetchone()

                cur.execute("""
                    SELECT
                        TO_CHAR(d.data, 'DD/MM'),
                        COALESCE(SUM(v.valor_total), 0)
                    FROM (
                        SELECT generate_series(
                            CURRENT_DATE - %s,
                            CURRENT_DATE,
                            '1 day'::interval
                        )::date AS data
                    ) d
                    LEFT JOIN vendas v
                        ON DATE(v.data_venda) = d.data
                        AND v.id_empresa = %s
                    GROUP BY d.data
                    ORDER BY d.data
                """, (dias - 1, id_empresa))

                grafico = cur.fetchall()

        return {
            "faturamento": float(faturamento or 0),
            "total_vendas": int(total_vendas or 0),
            "lucro": float(lucro or 0),
            "dias_grafico": [l[0] for l in grafico],
            "valores_grafico": [float(l[1]) for l in grafico],
        }

    except Exception as e:
        log_erro(f"Erro ao obter resumo de vendas: {e}")

        return {
            "faturamento": 0.0,
            "total_vendas": 0,
            "lucro": 0.0,
            "dias_grafico": [],
            "valores_grafico": [],
        }
# =========================================================
# REGISTRAR VENDA
# =========================================================
def registrar_venda(
    id_produto: int,
    quantidade: int,
    valor_total: float,
    usuario: str = "Sistema",
) -> bool:

    try:

        id_empresa = get_empresa_id()
        if not id_empresa:
            return False

        custo_unitario = calcular_custo_receita(id_produto)

        lucro_total = (
            float(valor_total)
            - (float(custo_unitario) * float(quantidade))
        )

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =====================================
                # BUSCA RECEITA
                # =====================================
                cur.execute("""
                    SELECT id_materia_prima, id_subproduto, quantidade_utilizada
                    FROM receitas
                    WHERE id_produto = %s
                    AND id_empresa = %s
                """, (id_produto, id_empresa))

                ingredientes = cur.fetchall()

                # =====================================
                # VALIDA ESTOQUE PRODUTO FINAL
                # =====================================
                saldo_produto = obter_saldo_produto(id_produto)

                if saldo_produto < quantidade:
                    raise ValueError(
                        f"Produto sem estoque suficiente. "
                        f"Disponível: {saldo_produto}"
                    )

                # =====================================
                # VALIDA INSUMOS
                # =====================================
                for id_mp, id_sub, qtd_util in ingredientes:

                    qtd_necessaria = float(qtd_util) * float(quantidade)

                    if id_mp:

                        saldo_mp = obter_saldo_materia_prima(id_mp)

                        if saldo_mp < qtd_necessaria:
                            raise ValueError(
                                f"Matéria-prima sem estoque. "
                                f"Necessário: {qtd_necessaria} "
                                f"Disponível: {saldo_mp}"
                            )

                    if id_sub:

                        saldo_sub = obter_saldo_subproduto(id_sub)

                        if saldo_sub < qtd_necessaria:
                            raise ValueError(
                                f"Subproduto sem estoque. "
                                f"Necessário: {qtd_necessaria} "
                                f"Disponível: {saldo_sub}"
                            )

                # =====================================
                # REGISTRA VENDA
                # =====================================
                cur.execute("""
                    INSERT INTO vendas
                    (
                        valor_total,
                        lucro,
                        canal_venda,
                        usuario,
                        id_empresa
                    )
                    VALUES (%s, %s, 'Sistema', %s, %s)
                    RETURNING id_venda
                """, (
                    valor_total,
                    lucro_total,
                    usuario,
                    id_empresa
                ))

                id_venda = cur.fetchone()[0]

                # =====================================
                # BUSCA PREÇO
                # =====================================
                cur.execute("""
                    SELECT preco_venda
                    FROM produtos
                    WHERE id_produto = %s
                    AND id_empresa = %s
                """, (id_produto, id_empresa))

                row = cur.fetchone()

                if not row:
                    raise ValueError(f"Produto ID {id_produto} não encontrado.")

                preco_unitario = float(row[0])

                # =====================================
                # ITEM VENDA
                # =====================================
                cur.execute("""
                    INSERT INTO itens_venda
                    (
                        id_venda,
                        id_produto,
                        quantidade,
                        valor_unitario,
                        id_empresa
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    id_venda,
                    id_produto,
                    quantidade,
                    preco_unitario,
                    id_empresa
                ))

                # =====================================
                # SAÍDA PRODUTO FINAL
                # =====================================
                cur.execute("""
                    INSERT INTO movimentacao_estoque
                    (
                        id_produto,
                        tipo_movimento,
                        quantidade,
                        observacao,
                        id_empresa
                    )
                    VALUES (%s, 'saida', %s, %s, %s)
                """, (
                    id_produto,
                    quantidade,
                    f"Venda ID {id_venda}",
                    id_empresa
                ))

                # =====================================
                # BAIXA INSUMOS
                # =====================================
                for id_mp, id_sub, qtd_util in ingredientes:

                    qtd_baixa = float(qtd_util) * float(quantidade)

                    if id_mp:

                        cur.execute("""
                            INSERT INTO movimentacao_estoque
                            (
                                id_materia_prima,
                                tipo_movimento,
                                quantidade,
                                observacao,
                                id_empresa
                            )
                            VALUES (%s, 'saida', %s, %s, %s)
                        """, (
                            id_mp,
                            qtd_baixa,
                            f"Venda ID {id_venda}",
                            id_empresa
                        ))

                    if id_sub:

                        cur.execute("""
                            INSERT INTO movimentacao_estoque
                            (
                                id_subproduto,
                                tipo_movimento,
                                quantidade,
                                observacao,
                                id_empresa
                            )
                            VALUES (%s, 'saida', %s, %s, %s)
                        """, (
                            id_sub,
                            qtd_baixa,
                            f"Venda ID {id_venda}",
                            id_empresa
                        ))

        log_info(f"Venda {id_venda} registrada - Empresa {id_empresa}")

        return True

    except Exception as e:
        log_erro(f"Erro ao registrar venda (Prod {id_produto}): {e}")
        return False


# =========================================================
# LISTAR VENDAS RECENTES
# =========================================================
def listar_vendas_recentes(limite: int = 10) -> list[dict]:

    try:
        from modules.tenant import get_empresa_id

        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        v.id_venda,
                        p.nome,
                        iv.quantidade,
                        v.valor_total,
                        v.data_venda
                    FROM vendas v
                    JOIN itens_venda iv
                        ON iv.id_venda = v.id_venda
                        AND iv.id_empresa = v.id_empresa
                    JOIN produtos p
                        ON p.id_produto = iv.id_produto
                        AND iv.id_empresa = v.id_empresa
                    WHERE v.id_empresa = %s
                    ORDER BY v.data_venda DESC
                    LIMIT %s
                    """,
                    (
                        id_empresa,
                        limite
                    ),
                )

                rows = cur.fetchall()

        return [
            {
                "id_venda": r[0],
                "nome_produto": r[1],
                "quantidade": r[2],
                "valor_total": float(r[3]),
                "data": r[4].strftime("%d/%m/%Y %H:%M") if r[4] else "-",
            }
            for r in rows
        ]

    except Exception as e:

        log_erro(f"Erro ao listar vendas recentes: {e}")

        return []

# =========================================================
# EXCLUIR / ESTORNAR VENDA
# =========================================================
def excluir_venda(id_venda: int) -> bool:

    try:
        from modules.tenant import get_empresa_id

        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:

            with conn.cursor() as cur:

                # =====================================
                # VERIFICA SE A VENDA EXISTE
                # =====================================

                cur.execute(
                    """
                    SELECT 1
                    FROM vendas
                    WHERE id_venda = %s
                    AND id_empresa = %s
                    """,
                    (id_venda, id_empresa)
                )

                if not cur.fetchone():

                    log_info(
                        f"Venda {id_venda} não encontrada para empresa {id_empresa}."
                    )

                    return False

                # =====================================
                # BUSCA ITENS VENDIDOS
                # =====================================

                cur.execute(
                    """
                    SELECT
                        id_produto,
                        quantidade
                    FROM itens_venda
                    WHERE id_venda = %s
                    AND id_empresa = %s
                    """,
                    (id_venda, id_empresa)
                )

                itens = cur.fetchall()

                # =====================================
                # DEVOLVE INSUMOS AO ESTOQUE
                # =====================================

                for id_produto, quantidade_vendida in itens:

                    cur.execute(
                        """
                        SELECT
                            id_materia_prima,
                            id_subproduto,
                            quantidade_utilizada
                        FROM receitas
                        WHERE id_produto = %s
                        AND id_empresa = %s
                        """,
                        (id_produto, id_empresa)
                    )

                    ingredientes = cur.fetchall()

                    for id_mp, id_subproduto, qtd_receita in ingredientes:

                        quantidade_estorno = float(qtd_receita) * float(quantidade_vendida)

                        # =========================
                        # MATÉRIA-PRIMA
                        # =========================

                        if id_mp:

                            cur.execute(
                                """
                                INSERT INTO movimentacao_estoque
                                (
                                    id_materia_prima,
                                    tipo_movimento,
                                    quantidade,
                                    observacao,
                                    id_empresa
                                )
                                VALUES (%s, 'entrada', %s, %s, %s)
                                """,
                                (
                                    id_mp,
                                    quantidade_estorno,
                                    f"ESTORNO VENDA {id_venda}",
                                    id_empresa
                                )
                            )

                        # =========================
                        # SUBPRODUTO
                        # =========================

                        if id_subproduto:

                            cur.execute(
                                """
                                INSERT INTO movimentacao_estoque
                                (
                                    id_subproduto,
                                    tipo_movimento,
                                    quantidade,
                                    observacao,
                                    id_empresa
                                )
                                VALUES (%s, 'entrada', %s, %s, %s)
                                """,
                                (
                                    id_subproduto,
                                    quantidade_estorno,
                                    f"ESTORNO VENDA {id_venda}",
                                    id_empresa
                                )
                            )

                # =====================================
                # REMOVE ITENS
                # =====================================

                cur.execute(
                    """
                    DELETE FROM itens_venda
                    WHERE id_venda = %s
                    AND id_empresa = %s
                    """,
                    (id_venda, id_empresa)
                )

                # =====================================
                # REMOVE VENDA
                # =====================================

                cur.execute(
                    """
                    DELETE FROM vendas
                    WHERE id_venda = %s
                    AND id_empresa = %s
                    """,
                    (id_venda, id_empresa)
                )

        log_info(
            f"Venda {id_venda} excluída com estorno de estoque. Empresa: {id_empresa}"
        )

        return True

    except Exception as e:

        log_erro(f"Erro ao excluir venda {id_venda}: {e}")

        return False


# =========================================================
# CUSTO TOTAL DAS VENDAS
# =========================================================
def obter_custo_total_vendas(dias: int = 30) -> float:

    try:
        from modules.tenant import get_empresa_id

        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        data_inicio = datetime.now() - timedelta(days=dias)

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(lucro), 0),
                        COALESCE(SUM(valor_total), 0)
                    FROM vendas
                    WHERE data_venda >= %s
                    AND id_empresa = %s
                    """,
                    (data_inicio, id_empresa),
                )

                lucro_total, faturamento = cur.fetchone()

        return round(
            float(faturamento or 0) - float(lucro_total or 0),
            2
        )

    except Exception as e:

        log_erro(
            f"Erro ao calcular custo total das vendas: {e}"
        )

        return 0.0