from modules.db import conectar

# =========================================================
# CADASTRAR / ATUALIZAR INGREDIENTE NA RECEITA
# =========================================================
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
            """, (float(quantidade), id_produto, id_materia_prima))
        else:
            cursor.execute("""
                INSERT INTO receitas (id_produto, id_materia_prima, quantidade_utilizada)
                VALUES (%s, %s, %s)
            """, (id_produto, id_materia_prima, float(quantidade)))

        con.commit()
        return True

    except Exception as e:
        print(f"Erro ao salvar receita: {e}")
        return False

    finally:
        if con:
            con.close()


# =========================================================
# LISTAR INGREDIENTES DE UM PRODUTO
# =========================================================
def listar_itens_receita(id_produto):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            SELECT 
                mp.id_materia_prima,
                mp.nome,
                r.quantidade_utilizada,
                mp.unidade_medida,
                mp.preco_unitario
            FROM receitas r
            JOIN materia_prima mp 
                ON mp.id_materia_prima = r.id_materia_prima
            WHERE r.id_produto = %s
            ORDER BY mp.nome ASC
        """, (id_produto,))

        return cursor.fetchall()

    except Exception as e:
        print(f"Erro ao listar receita: {e}")
        return []

    finally:
        if con:
            con.close()


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
            return True  # produto sem receita

        for id_mp, qtd_necessaria in ingredientes:
            estoque_atual = calcular_estoque(id_mp)

            if estoque_atual < (qtd_necessaria * quantidade_venda):
                return False

        return True

    except Exception as e:
        print(f"Erro validar estoque: {e}")
        return False

    finally:
        if con:
            con.close()


# =========================================================
# CALCULAR CUSTO TOTAL DO PRODUTO
# =========================================================
def calcular_custo_receita(id_produto):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            SELECT r.quantidade_utilizada, mp.preco_unitario
            FROM receitas r
            JOIN materia_prima mp 
                ON mp.id_materia_prima = r.id_materia_prima
            WHERE r.id_produto = %s
        """, (id_produto,))

        linhas = cursor.fetchall()

        total = 0.0

        for qtd, preco in linhas:
            total += float(qtd or 0) * float(preco or 0)

        return round(total, 2)

    except Exception as e:
        print(f"Erro ao calcular custo: {e}")
        return 0.0

    finally:
        if con:
            con.close()


# =========================================================
# LISTAR INGREDIENTES SIMPLES (para importações)
# =========================================================
def listar_ingredientes_por_produto(id_produto):
    """
    Usado em importação/preview
    """
    return listar_itens_receita(id_produto)