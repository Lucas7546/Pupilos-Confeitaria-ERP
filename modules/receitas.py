from modules.db import conectar


# =========================================================
# CADASTRAR / ATUALIZAR RECEITA
# =========================================================
def cadastrar_receita(id_produto, id_materia_prima, quantidade):
    con = None
    try:
        con = conectar()
        cur = con.cursor()

        cur.execute("""
            SELECT 1 FROM receitas
            WHERE id_produto = %s AND id_materia_prima = %s
        """, (id_produto, id_materia_prima))

        existe = cur.fetchone()

        if existe:
            cur.execute("""
                UPDATE receitas
                SET quantidade_utilizada = %s
                WHERE id_produto = %s AND id_materia_prima = %s
            """, (float(quantidade), id_produto, id_materia_prima))
        else:
            cur.execute("""
                INSERT INTO receitas (id_produto, id_materia_prima, quantidade_utilizada)
                VALUES (%s, %s, %s)
            """, (id_produto, id_materia_prima, float(quantidade)))

        con.commit()
        return True

    except Exception as e:
        print(f"Erro receita: {e}")
        return False

    finally:
        if con:
            con.close()


# =========================================================
# LISTAR RECEITA COMPLETA
# =========================================================
def listar_itens_receita(id_produto):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()
        cursor.execute("""
            SELECT 
                mp.id_materia_prima, mp.nome, r.quantidade_utilizada, mp.unidade_medida, mp.preco_unitario
            FROM receitas r
            JOIN materia_prima mp ON mp.id_materia_prima = r.id_materia_prima
            WHERE r.id_produto = %s
            ORDER BY mp.nome ASC
        """, (id_produto,))
        return cursor.fetchall()
    finally:
        if con: con.close()


# =========================================================
# VALIDAR ESTOQUE ANTES DA VENDA
# =========================================================
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

        if not ingredientes:
            return True

        for id_mp, qtd_necessaria in ingredientes:
            estoque_atual = calcular_estoque(id_mp) or 0

            if estoque_atual < (float(qtd_necessaria) * float(quantidade_venda)):
                return False

        return True

    except Exception as e:
        print(f"Erro validar estoque: {e}")
        return False

    finally:
        if con:
            con.close()


# =========================================================
# CALCULAR CUSTO TOTAL DA RECEITA
# =========================================================
def calcular_custo_receita(id_produto):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()
        cursor.execute("""
            SELECT r.quantidade_utilizada, mp.preco_unitario
            FROM receitas r
            JOIN materia_prima mp ON mp.id_materia_prima = r.id_materia_prima
            WHERE r.id_produto = %s
        """, (id_produto,))
        linhas = cursor.fetchall()
        total = sum(float(qtd or 0) * float(preco or 0) for qtd, preco in linhas)
        return round(total, 2)
    finally:
        if con: con.close()


# =========================================================
# LISTAGEM SIMPLES (IMPORTAÇÃO / FRONT)
# =========================================================
def listar_ingredientes_por_produto(id_produto):
    return listar_itens_receita(id_produto)