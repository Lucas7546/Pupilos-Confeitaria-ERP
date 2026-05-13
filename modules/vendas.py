from datetime import datetime
from modules.db import conectar

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