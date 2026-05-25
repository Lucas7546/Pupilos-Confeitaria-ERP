from datetime import datetime, timedelta
from modules.db import conectar
from utils.logger import log_info, log_erro
# No topo do vendas.py
from modules.receitas import (
    validar_estoque_suficiente, 
    calcular_custo_receita, 
    cadastrar_receita, 
    listar_itens_receita
)

# ===================================================
# RESUMO PARA O DASHBOARD
# ===================================================
def obter_resumo_periodo(dias=7):
    try:
        data_inicio = datetime.now() - timedelta(days=dias)
        with conectar() as con:
            with con.cursor() as cursor:
                # Resumo Geral
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(valor_total), 0),
                        COUNT(id_venda),
                        COALESCE(SUM(lucro), 0)
                    FROM vendas
                    WHERE data_venda >= %s
                """, (data_inicio,))
                faturamento, total_vendas, lucro = cursor.fetchone()

                # Gráfico
                cursor.execute("""
                    SELECT TO_CHAR(DATE(data_venda), 'DD/MM'), COALESCE(SUM(valor_total), 0)
                    FROM vendas
                    WHERE data_venda >= %s
                    GROUP BY DATE(data_venda)
                    ORDER BY DATE(data_venda)
                """, (data_inicio,))
                grafico = cursor.fetchall()

        return {
            "faturamento": float(faturamento or 0),
            "total_vendas": int(total_vendas or 0),
            "lucro": float(lucro or 0),
            "dias_grafico": [l[0] for l in grafico],
            "valores_grafico": [float(l[1]) for l in grafico]
        }
    except Exception as e:
        log_erro(f"Erro ao obter resumo de vendas: {e}")
        return {"faturamento": 0.0, "total_vendas": 0, "lucro": 0.0, "dias_grafico": [], "valores_grafico": []}

# ===================================================
# REGISTRAR VENDA
# ===================================================
def registrar_venda(id_produto, quantidade, valor_total, usuario="Sistema"):
    try:
        with conectar() as con:
            with con.cursor() as cursor:
                custo_unitario = calcular_custo_receita(id_produto)
                lucro_total = float(valor_total) - (float(custo_unitario) * float(quantidade))

                # Registrar Venda
                cursor.execute("""
                    INSERT INTO vendas (valor_total, lucro, canal_venda, usuario)
                    VALUES (%s, %s, 'Sistema', %s) RETURNING id_venda
                """, (valor_total, lucro_total, usuario))
                id_venda = cursor.fetchone()[0]

                # Preço Unitário
                cursor.execute("SELECT preco_venda FROM produtos WHERE id_produto = %s", (id_produto,))
                preco_unitario = float(cursor.fetchone()[0])

                # Item Venda
                cursor.execute("""
                    INSERT INTO itens_venda (id_venda, id_produto, quantidade, valor_unitario)
                    VALUES (%s, %s, %s, %s)
                """, (id_venda, id_produto, quantidade, preco_unitario))

                # Baixa Estoque
                cursor.execute("SELECT id_materia_prima, quantidade_utilizada FROM receitas WHERE id_produto = %s", (id_produto,))
                for id_mp, qtd_receita in cursor.fetchall():
                    cursor.execute("""
                        INSERT INTO movimentacao_estoque (id_materia_prima, tipo_movimento, quantidade, observacao)
                        VALUES (%s, 'saida', %s, %s)
                    """, (id_mp, float(qtd_receita) * float(quantidade), f'Venda ID {id_venda}'))

            con.commit()
            log_info(f"Venda {id_venda} registrada com sucesso para o produto {id_produto}.")
            return True
    except Exception as e:
        log_erro(f"Erro ao registrar venda (Prod: {id_produto}): {e}")
        return False

# ===================================================
# LISTAR VENDAS RECENTES
# ===================================================
def listar_vendas_recentes(limite=10):
    try:
        with conectar() as con:
            with con.cursor() as cursor:
                cursor.execute("""
                    SELECT v.id_venda, p.nome, iv.quantidade, v.valor_total, v.data_venda
                    FROM vendas v
                    JOIN itens_venda iv ON iv.id_venda = v.id_venda
                    JOIN produtos p ON p.id_produto = iv.id_produto
                    ORDER BY v.data_venda DESC LIMIT %s
                """, (limite,))
                return [{"id_venda": v[0], "nome_produto": v[1], "quantidade": v[2], "valor_total": float(v[3]), "data": v[4].strftime("%d/%m/%Y %H:%M")} for v in cursor.fetchall()]
    except Exception as e:
        log_erro(f"Erro ao listar vendas recentes: {e}")
        return []

# ===================================================
# CUSTO TOTAL DAS VENDAS
# ===================================================
def obter_custo_total_vendas(dias=30):
    try:
        data_inicio = datetime.now() - timedelta(days=dias)
        with conectar() as con:
            with con.cursor() as cursor:
                cursor.execute("SELECT COALESCE(SUM(lucro), 0), COALESCE(SUM(valor_total), 0) FROM vendas WHERE data_venda >= %s", (data_inicio,))
                lucro_total, faturamento = cursor.fetchone()
                return round(float(faturamento) - float(lucro_total), 2)
    except Exception as e:
        log_erro(f"Erro ao calcular custo total das vendas: {e}")
        return 0.0


# ===================================================
# LISTAR DESPESAS
# ===================================================
def listar_despesas(dias=30):
    try:
        data_inicio = datetime.now() - timedelta(days=dias)
        with conectar() as con:
            with con.cursor() as cursor:
                cursor.execute("SELECT id_despesa, descricao, valor, categoria, data_despesa FROM despesas WHERE data_despesa >= %s ORDER BY data_despesa DESC", (data_inicio,))
                return cursor.fetchall()
    except Exception as e:
        log_erro(f"Erro ao listar despesas: {e}")
        return []
    
def excluir_venda(id_venda):
    """Exclui venda e realiza rollback do estoque das matérias-primas."""

    try:
        with conectar() as conn:
            with conn.cursor() as cursor:

                # =========================================
                # VERIFICA SE VENDA EXISTE
                # =========================================
                cursor.execute("""
                    SELECT 1
                    FROM vendas
                    WHERE id_venda = %s
                """, (id_venda,))

                if not cursor.fetchone():
                    log_info(f"Venda {id_venda} não encontrada.")
                    return False

                # =========================================
                # BUSCA ITENS DA VENDA
                # =========================================
                cursor.execute("""
                    SELECT id_produto, quantidade
                    FROM itens_venda
                    WHERE id_venda = %s
                """, (id_venda,))

                itens = cursor.fetchall()

                if not itens:
                    log_info(f"Venda {id_venda} sem itens vinculados.")

                # =========================================
                # ROLLBACK DE ESTOQUE (MATÉRIA-PRIMA)
                # =========================================
                for id_produto, quantidade_vendida in itens:

                    cursor.execute("""
                        SELECT id_materia_prima, quantidade_utilizada
                        FROM receitas
                        WHERE id_produto = %s
                    """, (id_produto,))

                    ingredientes = cursor.fetchall()

                    for id_mp, qtd_receita in ingredientes:

                        qtd_retorno = float(qtd_receita) * float(quantidade_vendida)

                        cursor.execute("""
                            INSERT INTO movimentacao_estoque (
                                id_materia_prima,
                                tipo_movimento,
                                quantidade,
                                observacao
                            )
                            VALUES (%s, 'entrada', %s, %s)
                        """, (
                            id_mp,
                            qtd_retorno,
                            f'ROLLBACK AUTOMÁTICO VENDA ID {id_venda}'
                        ))

                # =========================================
                # REMOVE ITENS DA VENDA
                # =========================================
                cursor.execute("""
                    DELETE FROM itens_venda
                    WHERE id_venda = %s
                """, (id_venda,))

                # =========================================
                # REMOVE VENDA
                # =========================================
                cursor.execute("""
                    DELETE FROM vendas
                    WHERE id_venda = %s
                """, (id_venda,))

                conn.commit()

                log_info(f"Venda {id_venda} excluída com rollback realizado.")
                return True

    except Exception as e:
        log_erro(f"Erro ao excluir venda {id_venda}: {e}")
        return False