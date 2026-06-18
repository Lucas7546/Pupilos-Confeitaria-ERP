from datetime import datetime, timedelta
from modules.receitas import calcular_custo_receita, validar_estoque_suficiente
from modules.tenant_db import db_conn
from modules.tenant import get_empresa_id
from flask_login import current_user
from utils.logger import log_info, log_erro
from flask import g
from modules.estoque import obter_saldo_subproduto, obter_saldo_materia_prima, obter_saldo_produto


# =========================================================
# RESUMO PARA O DASHBOARD
# =========================================================
def obter_resumo_periodo(dias: int = 7) -> dict:
    try:
        from datetime import datetime, timedelta
        from modules.tenant import get_empresa_id

        id_empresa = get_empresa_id()
        if not id_empresa:
            raise Exception("Empresa não definida")

        data_inicio = datetime.now() - timedelta(days=dias)

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =========================
                # RESUMO FINANCEIRO
                # =========================
                cur.execute("""
                    SELECT
                        COALESCE(SUM(valor_total), 0),
                        COUNT(id_venda),
                        COALESCE(SUM(lucro), 0)
                    FROM vendas
                    WHERE id_empresa = %s
                      AND data_venda IS NOT NULL
                      AND data_venda >= %s
                """, (id_empresa, data_inicio))

                faturamento, total_vendas, lucro = cur.fetchone()

                # =========================
                # GRÁFICO DIÁRIO
                # =========================
                cur.execute("""
                    SELECT
                        TO_CHAR(d.data, 'DD/MM'),
                        COALESCE(SUM(v.valor_total), 0)
                    FROM (
                        SELECT generate_series(
                            CURRENT_DATE - (%s - 1),
                            CURRENT_DATE,
                            INTERVAL '1 day'
                        )::date AS data
                    ) d
                    LEFT JOIN vendas v
                        ON v.id_empresa = %s
                       AND v.data_venda IS NOT NULL
                       AND v.data_venda::date = d.data
                    GROUP BY d.data
                    ORDER BY d.data
                """, (dias, id_empresa))

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

    conn = None

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            raise ValueError("Empresa não encontrada")

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =========================
                # VALIDAÇÃO ESTOQUE
                # =========================
                if not validar_estoque_suficiente(id_produto, quantidade):
                    raise ValueError("Estoque insuficiente")

                # =========================
                # BUSCA RECEITA
                # =========================
                cur.execute("""
                    SELECT id_materia_prima, id_subproduto, quantidade_utilizada
                    FROM receitas
                    WHERE id_produto = %s
                      AND id_empresa = %s
                """, (id_produto, id_empresa))

                ingredientes = cur.fetchall()

                # =========================
                # PRODUTO
                # =========================
                cur.execute("""
                    SELECT preco_venda
                    FROM produtos
                    WHERE id_produto = %s
                      AND id_empresa = %s
                """, (id_produto, id_empresa))

                row = cur.fetchone()
                if not row:
                    raise ValueError("Produto não encontrado")

                preco_unitario = float(row[0])
                lucro_total = float(valor_total) - (preco_unitario * float(quantidade))

                # =========================
                # VENDA
                # =========================
                cur.execute("""
                    INSERT INTO vendas (
                        valor_total,
                        lucro,
                        canal_venda,
                        usuario,
                        id_empresa,
                        data_venda
                    )
                    VALUES (%s, %s, 'Sistema', %s, %s, NOW())
                    RETURNING id_venda
                """, (
                    valor_total,
                    lucro_total,
                    usuario,
                    id_empresa
                ))

                id_venda = cur.fetchone()[0]

                # =========================
                # ITEM VENDA
                # =========================
                cur.execute("""
                    INSERT INTO itens_venda (
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

                # =========================
                # MOVIMENTAÇÃO PRODUTO FINAL
                # =========================
                cur.execute("""
                    INSERT INTO movimentacao_estoque (
                        id_produto,
                        tipo_movimento,
                        quantidade,
                        observacao,
                        usuario,
                        id_empresa
                    )
                    VALUES (%s, 'saida', %s, %s, %s, %s)
                """, (
                    id_produto,
                    quantidade,
                    f"Venda ID {id_venda}",
                    usuario,
                    id_empresa
                ))

                # =========================
                # BAIXA INSUMOS
                # =========================
                for id_mp, id_sub, qtd_util in ingredientes:

                    qtd_baixa = float(qtd_util) * float(quantidade)

                    if id_mp:
                        cur.execute("""
                            INSERT INTO movimentacao_estoque (
                                id_materia_prima,
                                tipo_movimento,
                                quantidade,
                                observacao,
                                usuario,
                                id_empresa
                            )
                            VALUES (%s, 'saida', %s, %s, %s, %s)
                        """, (
                            id_mp,
                            qtd_baixa,
                            f"Venda ID {id_venda}",
                            usuario,
                            id_empresa
                        ))

                    if id_sub:
                        cur.execute("""
                            INSERT INTO movimentacao_estoque (
                                id_subproduto,
                                tipo_movimento,
                                quantidade,
                                observacao,
                                usuario,
                                id_empresa
                            )
                            VALUES (%s, 'saida', %s, %s, %s, %s)
                        """, (
                            id_sub,
                            qtd_baixa,
                            f"Venda ID {id_venda}",
                            usuario,
                            id_empresa
                        ))

        return True

    except Exception as e:
        log_erro(f"ERRO VENDA COMPLETO (Prod {id_produto}): {repr(e)}")

        if conn:
            try:
                conn.rollback()
            except:
                pass
  
        return False

# =========================================================
# LISTAR VENDAS RECENTES
# =========================================================
def listar_vendas_recentes(limite: int = 10) -> list[dict]:
    try:
        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        v.id_venda,
                        p.nome,
                        iv.quantidade,
                        v.valor_total,
                        v.data_venda
                    FROM vendas v

                    JOIN itens_venda iv
                        ON iv.id_venda = v.id_venda
                       AND iv.id_empresa = %s

                    JOIN produtos p
                        ON p.id_produto = iv.id_produto
                       AND p.id_empresa = %s

                    WHERE v.id_empresa = %s

                    ORDER BY v.data_venda DESC
                    LIMIT %s
                """, (id_empresa, id_empresa, id_empresa, limite))

                rows = cur.fetchall()

        return [
            {
                "id_venda": r[0],
                "nome_produto": r[1],
                "quantidade": r[2],
                "valor_total": float(r[3]),
                "data": r[4].strftime("%d/%m/%Y %H:%M") if r[4] else "-"
            }
            for r in rows
        ]

    except Exception as e:
        log_erro(f"Erro vendas recentes: {e}")
        return []

# =========================================================
# EXCLUIR / ESTORNAR VENDA
# =========================================================
def excluir_venda(id_venda: int) -> bool:
    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return False

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =========================
                # valida venda
                # =========================
                cur.execute("""
                    SELECT 1
                    FROM vendas
                    WHERE id_venda = %s
                      AND id_empresa = %s
                """, (id_venda, id_empresa))

                if not cur.fetchone():
                    return False

                # =========================
                # itens da venda
                # =========================
                cur.execute("""
                    SELECT id_produto, quantidade
                    FROM itens_venda
                    WHERE id_venda = %s
                      AND id_empresa = %s
                """, (id_venda, id_empresa))

                itens = cur.fetchall()

                # =========================
                # ESTORNO INSUMOS
                # =========================
                for id_produto, qtd_vendida in itens:

                    cur.execute("""
                        SELECT id_materia_prima, id_subproduto, quantidade_utilizada
                        FROM receitas
                        WHERE id_produto = %s
                          AND id_empresa = %s
                    """, (id_produto, id_empresa))

                    ingredientes = cur.fetchall()

                    for id_mp, id_sub, qtd_util in ingredientes:

                        qtd_estorno = float(qtd_util) * float(qtd_vendida)

                        if id_mp:
                            cur.execute("""
                                INSERT INTO movimentacao_estoque
                                (id_empresa, id_materia_prima, tipo_movimento, quantidade, observacao)
                                VALUES (%s, %s, 'entrada', %s, %s)
                            """, (
                                id_empresa,
                                id_mp,
                                qtd_estorno,
                                f"ESTORNO VENDA {id_venda}"
                            ))

                        if id_sub:
                            cur.execute("""
                                INSERT INTO movimentacao_estoque
                                (id_empresa, id_subproduto, tipo_movimento, quantidade, observacao)
                                VALUES (%s, %s, 'entrada', %s, %s)
                            """, (
                                id_empresa,
                                id_sub,
                                qtd_estorno,
                                f"ESTORNO VENDA {id_venda}"
                            ))

                    # =========================
                    # ESTORNO PRODUTO FINAL (CORREÇÃO)
                    # =========================
                    cur.execute("""
                        INSERT INTO movimentacao_estoque
                        (id_empresa, id_produto, tipo_movimento, quantidade, observacao)
                        VALUES (%s, %s, 'entrada', %s, %s)
                    """, (
                        id_empresa,
                        id_produto,
                        float(qtd_vendida),
                        f"ESTORNO VENDA {id_venda}"
                    ))

                # =========================
                # remove dados
                # =========================
                cur.execute("""
                    DELETE FROM itens_venda
                    WHERE id_venda = %s
                      AND id_empresa = %s
                """, (id_venda, id_empresa))

                cur.execute("""
                    DELETE FROM vendas
                    WHERE id_venda = %s
                      AND id_empresa = %s
                """, (id_venda, id_empresa))

        log_info(f"Venda {id_venda} excluída com estorno - Empresa {id_empresa}")
        return True

    except Exception as e:
        log_erro(f"Erro ao excluir venda {id_venda}: {e}")
        return False


# =========================================================
# CUSTO TOTAL DAS VENDAS
# =========================================================
def obter_custo_total_vendas(dias: int = 30) -> float:
    try:
        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        data_inicio = datetime.now() - timedelta(days=dias)

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        COALESCE(SUM(lucro), 0),
                        COALESCE(SUM(valor_total), 0)
                    FROM vendas
                    WHERE data_venda >= %s
                      AND id_empresa = %s
                """, (data_inicio, id_empresa))

                lucro, faturamento = cur.fetchone()

        return round(float(faturamento or 0) - float(lucro or 0), 2)

    except Exception as e:
        log_erro(f"Erro custo vendas: {e}")
        return 0.0