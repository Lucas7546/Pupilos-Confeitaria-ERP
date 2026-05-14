from datetime import datetime, timedelta
from modules.db import conectar

# ===================================================
# RESUMO PARA O DASHBOARD (A que estava faltando!)
# ===================================================
def obter_resumo_periodo(dias=7):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()
        
        # Define a data de início (hoje menos X dias)
        data_inicio = datetime.now() - timedelta(days=dias)

        cursor.execute("""
            SELECT 
                COALESCE(SUM(valor_total), 0) as faturamento,
                COUNT(id_venda) as total_vendas
            FROM vendas
            WHERE data_venda >= %s
        """, (data_inicio,))

        resultado = cursor.fetchone()
        return {
            "faturamento": float(resultado[0]),
            "vendas": int(resultado[1])
        }
    except Exception as e:
        print(f"Erro ao obter resumo: {e}")
        return {"faturamento": 0.0, "vendas": 0}
    finally:
        if con:
            con.close()

# ===================================================
# REGISTRAR VENDA
# ===================================================
def registrar_venda(id_produto, quantidade, valor_total, usuario="Sistema"):
    con = None

    try:
        con = conectar()
        cursor = con.cursor()

        # =====================================================
        # CALCULA CUSTO/LUCRO
        # =====================================================

        custo_unitario = calcular_custo_receita(id_produto)

        lucro_total = float(valor_total) - (
            float(custo_unitario) * float(quantidade)
        )

        # =====================================================
        # CRIA VENDA
        # =====================================================

        cursor.execute("""
            INSERT INTO vendas (
                valor_total,
                lucro,
                canal_venda,
                usuario
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id_venda
        """, (
            valor_total,
            lucro_total,
            'Sistema',
            usuario
        ))

        id_venda = cursor.fetchone()[0]

        # =====================================================
        # BUSCA PREÇO UNITÁRIO
        # =====================================================

        cursor.execute("""
            SELECT preco_venda
            FROM produtos
            WHERE id_produto = %s
        """, (id_produto,))

        preco_unitario = float(cursor.fetchone()[0])

        # =====================================================
        # SALVA ITEM VENDA
        # =====================================================

        cursor.execute("""
            INSERT INTO itens_venda (
                id_venda,
                id_produto,
                quantidade,
                valor_unitario
            )
            VALUES (%s, %s, %s, %s)
        """, (
            id_venda,
            id_produto,
            quantidade,
            preco_unitario
        ))

        # =====================================================
        # BAIXA ESTOQUE
        # =====================================================

        cursor.execute("""
            SELECT
                id_materia_prima,
                quantidade_utilizada
            FROM receitas
            WHERE id_produto = %s
        """, (id_produto,))

        ingredientes = cursor.fetchall()

        for id_mp, qtd_receita in ingredientes:

            qtd_saida = float(qtd_receita) * float(quantidade)

            cursor.execute("""
                INSERT INTO movimentacao_estoque (
                    id_materia_prima,
                    tipo_movimento,
                    quantidade,
                    observacao
                )
                VALUES (%s, 'saida', %s, %s)
            """, (
                id_mp,
                qtd_saida,
                f'Venda Produto ID {id_produto}'
            ))

        con.commit()

        return True

    except Exception as e:

        if con:
            con.rollback()

        print(f"Erro registrar_venda: {e}")

        return False

    finally:

        if con:
            con.close()

# ===================================================
# LISTAR VENDAS RECENTES
# ===================================================
def listar_vendas_recentes(limite=10):

    con = None

    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            SELECT
                v.id_venda,
                p.nome,
                iv.quantidade,
                v.valor_total,
                v.data_venda
            FROM vendas v

            JOIN itens_venda iv
                ON iv.id_venda = v.id_venda

            JOIN produtos p
                ON p.id_produto = iv.id_produto

            ORDER BY v.data_venda DESC

            LIMIT %s
        """, (limite,))

        return cursor.fetchall()

    finally:

        if con:
            con.close()
# ===================================================
# VALIDA ESTOQUE
# ===================================================
def validar_estoque_suficiente(id_produto, quantidade_venda):
    from modules.estoque import calcular_estoque

    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            SELECT id_materia_prima, quantidade_utilizada
            FROM receitas
            WHERE id_produto = %s
        """, (id_produto,))

        ingredientes = cursor.fetchall()

        for id_mp, qtd_necessaria in ingredientes:
            estoque_atual = calcular_estoque(id_mp)

            if estoque_atual < (qtd_necessaria * quantidade_venda):
                return False

        return True

    except Exception as e:
        print(f"Erro validação estoque: {e}")
        return False

    finally:
        if con:
            con.close()


# ===================================================
# CUSTO DA RECEITA
# ===================================================
def calcular_custo_receita(id_produto):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            SELECT r.quantidade_utilizada, mp.preco_unitario
            FROM receitas r
            JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
            WHERE r.id_produto = %s
        """, (id_produto,))

        linhas = cursor.fetchall()

        total = sum(float(q) * float(p) for q, p in linhas)

        return round(total, 2)

    except Exception as e:
        print(f"Erro custo receita: {e}")
        return 0.0

    finally:
        if con:
            con.close()


# ===================================================
# CADASTRAR / VINCULAR RECEITA
# ===================================================
def cadastrar_receita(id_produto, id_materia_prima, quantidade):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            SELECT id_receita
            FROM receitas
            WHERE id_produto = %s
            AND id_materia_prima = %s
        """, (id_produto, id_materia_prima))

        existe = cursor.fetchone()

        if existe:
            cursor.execute("""
                UPDATE receitas
                SET quantidade_utilizada = %s
                WHERE id_produto = %s
                AND id_materia_prima = %s
            """, (quantidade, id_produto, id_materia_prima))
        else:
            cursor.execute("""
                INSERT INTO receitas (id_produto, id_materia_prima, quantidade_utilizada)
                VALUES (%s, %s, %s)
            """, (id_produto, id_materia_prima, quantidade))

        con.commit()
        return True

    except Exception as e:
        print(f"Erro receita: {e}")
        return False

    finally:
        if con:
            con.close()


# ===================================================
# LISTAR RECEITA
# ===================================================
def listar_itens_receita(id_produto):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            SELECT mp.nome, r.quantidade_utilizada, mp.unidade_medida, mp.preco_unitario
            FROM receitas r
            JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
            WHERE r.id_produto = %s
            ORDER BY mp.nome ASC
        """, (id_produto,))

        return cursor.fetchall()

    finally:
        if con:
            con.close()


# ===================================================
# CUSTO TOTAL DAS VENDAS
# ===================================================
def obter_custo_total_vendas(dias=30):

    con = None

    try:

        con = conectar()
        cursor = con.cursor()

        data_inicio = datetime.now() - timedelta(days=dias)

        cursor.execute("""
            SELECT COALESCE(SUM(lucro), 0)
            FROM vendas
            WHERE data_venda >= %s
        """, (data_inicio,))

        lucro_total = float(cursor.fetchone()[0] or 0)

        cursor.execute("""
            SELECT COALESCE(SUM(valor_total), 0)
            FROM vendas
            WHERE data_venda >= %s
        """, (data_inicio,))

        faturamento = float(cursor.fetchone()[0] or 0)

        custo = faturamento - lucro_total

        return round(custo, 2)

    except Exception as e:

        print(f"Erro custo vendas: {e}")

        return 0.0

    finally:

        if con:
            con.close()


# ===================================================
# LISTAR DESPESAS
# ===================================================
def listar_despesas(dias=30):

    con = None

    try:

        con = conectar()
        cursor = con.cursor()

        data_inicio = datetime.now() - timedelta(days=dias)

        cursor.execute("""
            SELECT
                id_despesa,
                descricao,
                valor,
                categoria,
                data_despesa
            FROM despesas
            WHERE data_despesa >= %s
            ORDER BY data_despesa DESC
        """, (data_inicio,))

        return cursor.fetchall()

    except Exception as e:

        print(f"Erro listar despesas: {e}")

        return []

    finally:

        if con:
            con.close()