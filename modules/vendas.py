from datetime import datetime, timedelta

from modules.db import get_conn
from utils.logger import log_info, log_erro


# =========================================================
# RESUMO PARA O DASHBOARD
# =========================================================
def obter_resumo_periodo(dias: int = 7) -> dict:
    try:
        data_inicio = datetime.now() - timedelta(days=dias)
        with get_conn() as conn:
            with conn.cursor() as cur:
                
                # --- AQUI ESTAVA FALTANDO ESTA QUERY ---
                cur.execute(
                    """
                    SELECT 
                        COALESCE(SUM(valor_total), 0),
                        COUNT(id_venda),
                        COALESCE(SUM(lucro), 0)
                    FROM vendas
                    WHERE data_venda >= %s
                    """,
                    (data_inicio,),
                )
                faturamento, total_vendas, lucro = cur.fetchone()
                # ----------------------------------------

                # Query para o gráfico
                cur.execute(
                    """
                    SELECT 
                        TO_CHAR(d.data, 'DD/MM'), 
                        COALESCE(SUM(v.valor_total), 0)
                    FROM (
                        SELECT generate_series(CURRENT_DATE - %s, CURRENT_DATE, '1 day'::interval)::date AS data
                    ) d
                    LEFT JOIN vendas v ON DATE(v.data_venda) = d.data
                    GROUP BY d.data
                    ORDER BY d.data
                    """,
                    (dias - 1,),
                )
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
# Bug corrigido: toda a operação ocorre num único bloco com o mesmo
# cursor — o cursor original não é reaproveitado após fetchall interno.
# O rollback é feito automaticamente pelo get_conn() em caso de erro.
# =========================================================
def registrar_venda(
    id_produto: int,
    quantidade: int,
    valor_total: float,
    usuario: str = "Sistema",
) -> bool:

    from modules.receitas import calcular_custo_receita

    try:

        custo_unitario = calcular_custo_receita(id_produto)

        lucro_total = (
            float(valor_total)
            - (float(custo_unitario) * float(quantidade))
        )

        with get_conn() as conn:

            with conn.cursor() as cur:

                # =====================================
                # REGISTRA VENDA
                # =====================================

                cur.execute(
                    """
                    INSERT INTO vendas
                    (
                        valor_total,
                        lucro,
                        canal_venda,
                        usuario
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        'Sistema',
                        %s
                    )
                    RETURNING id_venda
                    """,
                    (
                        valor_total,
                        lucro_total,
                        usuario
                    )
                )

                id_venda = cur.fetchone()[0]

                # =====================================
                # BUSCA PREÇO UNITÁRIO
                # =====================================

                cur.execute(
                    """
                    SELECT preco_venda
                    FROM produtos
                    WHERE id_produto = %s
                    """,
                    (id_produto,)
                )

                row = cur.fetchone()

                if not row:
                    raise ValueError(
                        f"Produto ID {id_produto} não encontrado."
                    )

                preco_unitario = float(row[0])

                # =====================================
                # ITEM DA VENDA
                # =====================================

                cur.execute(
                    """
                    INSERT INTO itens_venda
                    (
                        id_venda,
                        id_produto,
                        quantidade,
                        valor_unitario
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        id_venda,
                        id_produto,
                        quantidade,
                        preco_unitario
                    )
                )

                # =====================================
                # SAÍDA DO PRODUTO FINAL
                # =====================================

                cur.execute(
                    """
                    INSERT INTO movimentacao_estoque
                    (
                        id_produto,
                        tipo_movimento,
                        quantidade,
                        observacao
                    )
                    VALUES
                    (
                        %s,
                        'saida',
                        %s,
                        %s
                    )
                    """,
                    (
                        id_produto,
                        quantidade,
                        f"Venda ID {id_venda}"
                    )
                )

                # =====================================
                # BUSCA RECEITA
                # =====================================

                cur.execute(
                    """
                    SELECT
                        id_materia_prima,
                        id_subproduto,
                        quantidade_utilizada
                    FROM receitas
                    WHERE id_produto = %s
                    """,
                    (id_produto,)
                )

                ingredientes = cur.fetchall()

                # =====================================
                # BAIXA INSUMOS
                # =====================================

                for (
                    id_materia_prima,
                    id_subproduto,
                    quantidade_utilizada
                ) in ingredientes:

                    qtd_baixa = (
                        float(quantidade_utilizada)
                        * float(quantidade)
                    )

                    # -----------------------------
                    # MATÉRIA-PRIMA
                    # -----------------------------

                    if id_materia_prima:

                        cur.execute(
                            """
                            INSERT INTO movimentacao_estoque
                            (
                                id_materia_prima,
                                tipo_movimento,
                                quantidade,
                                observacao
                            )
                            VALUES
                            (
                                %s,
                                'saida',
                                %s,
                                %s
                            )
                            """,
                            (
                                id_materia_prima,
                                qtd_baixa,
                                f"Venda ID {id_venda}"
                            )
                        )

                    # -----------------------------
                    # SUBPRODUTO
                    # -----------------------------

                    if id_subproduto:

                        cur.execute(
                            """
                            INSERT INTO movimentacao_estoque
                            (
                                id_subproduto,
                                tipo_movimento,
                                quantidade,
                                observacao
                            )
                            VALUES
                            (
                                %s,
                                'saida',
                                %s,
                                %s
                            )
                            """,
                            (
                                id_subproduto,
                                qtd_baixa,
                                f"Venda ID {id_venda}"
                            )
                        )

            conn.commit()

        log_info(
            f"Venda {id_venda} registrada - Produto {id_produto}"
        )

        return True

    except Exception as e:

        log_erro(
            f"Erro ao registrar venda (Prod {id_produto}): {e}"
        )

        
        return False


# =========================================================
# LISTAR VENDAS RECENTES
# =========================================================
def listar_vendas_recentes(limite: int = 10) -> list[dict]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT v.id_venda, p.nome, iv.quantidade, v.valor_total, v.data_venda
                    FROM vendas v
                    JOIN itens_venda iv ON iv.id_venda = v.id_venda
                    JOIN produtos p ON p.id_produto = iv.id_produto
                    ORDER BY v.data_venda DESC
                    LIMIT %s
                    """,
                    (limite,),
                )
                rows = cur.fetchall()

        return [
            {
                "id_venda": r[0],
                "nome_produto": r[1],
                "quantidade": r[2],
                "valor_total": float(r[3]),
                "data": r[4].strftime("%d/%m/%Y %H:%M"),
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

        with get_conn() as conn:

            with conn.cursor() as cur:

                # Verifica se existe
                cur.execute(
                    "SELECT 1 FROM vendas WHERE id_venda = %s",
                    (id_venda,)
                )

                if not cur.fetchone():
                    log_info(f"Venda {id_venda} não encontrada.")
                    return False

                # Busca itens vendidos
                cur.execute(
                    """
                    SELECT
                        id_produto,
                        quantidade
                    FROM itens_venda
                    WHERE id_venda = %s
                    """,
                    (id_venda,)
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
                        """,
                        (id_produto,)
                    )

                    ingredientes = cur.fetchall()

                    for (
                        id_mp,
                        id_subproduto,
                        qtd_receita
                    ) in ingredientes:

                        quantidade_estorno = (
                            float(qtd_receita)
                            * float(quantidade_vendida)
                        )

                        # -------------------------
                        # DEVOLVE MATÉRIA-PRIMA
                        # -------------------------

                        if id_mp:

                            cur.execute(
                                """
                                INSERT INTO movimentacao_estoque
                                (
                                    id_materia_prima,
                                    tipo_movimento,
                                    quantidade,
                                    observacao
                                )
                                VALUES
                                (
                                    %s,
                                    'entrada',
                                    %s,
                                    %s
                                )
                                """,
                                (
                                    id_mp,
                                    quantidade_estorno,
                                    f"ESTORNO VENDA {id_venda}"
                                )
                            )

                        # -------------------------
                        # DEVOLVE SUBPRODUTO
                        # -------------------------

                        if id_subproduto:

                            cur.execute(
                                """
                                INSERT INTO movimentacao_estoque
                                (
                                    id_subproduto,
                                    tipo_movimento,
                                    quantidade,
                                    observacao
                                )
                                VALUES
                                (
                                    %s,
                                    'entrada',
                                    %s,
                                    %s
                                )
                                """,
                                (
                                    id_subproduto,
                                    quantidade_estorno,
                                    f"ESTORNO VENDA {id_venda}"
                                )
                            )

                # =====================================
                # REMOVE VENDA
                # =====================================

                cur.execute(
                    "DELETE FROM itens_venda WHERE id_venda = %s",
                    (id_venda,)
                )

                cur.execute(
                    "DELETE FROM vendas WHERE id_venda = %s",
                    (id_venda,)
                )

            conn.commit()

        log_info(
            f"Venda {id_venda} excluída com estorno de estoque."
        )

        return True

    except Exception as e:

        log_erro(
            f"Erro ao excluir venda {id_venda}: {e}"
        )

        return False


# =========================================================
# CUSTO TOTAL DAS VENDAS
# =========================================================
def obter_custo_total_vendas(dias: int = 30) -> float:
    try:
        data_inicio = datetime.now() - timedelta(days=dias)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(lucro), 0), COALESCE(SUM(valor_total), 0) FROM vendas WHERE data_venda >= %s",
                    (data_inicio,),
                )
                lucro_total, faturamento = cur.fetchone()
        return round(float(faturamento) - float(lucro_total), 2)
    except Exception as e:
        log_erro(f"Erro ao calcular custo total das vendas: {e}")
        return 0.0
