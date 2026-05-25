from modules.db import conectar
from utils.logger import log_info, log_erro

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
        log_info(f"Receita atualizada: Produto {id_produto}, MP {id_materia_prima}, Qtd: {quantidade}")
        return True

    except Exception as e:
        log_erro(f"Erro ao cadastrar receita (Prod: {id_produto}, MP: {id_materia_prima}): {e}")
        return False
    finally:
        if con: con.close()

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
    except Exception as e:
        log_erro(f"Erro ao listar itens da receita (Prod: {id_produto}): {e}")
        return []
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
        log_erro(f"Erro ao validar estoque para venda (Prod: {id_produto}): {e}")
        return False
    finally:
        if con: con.close()

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
    except Exception as e:
        log_erro(f"Erro ao calcular custo da receita (Prod: {id_produto}): {e}")
        return 0.0
    finally:
        if con: con.close()

# =========================================================
# LISTAGEM SIMPLES
# =========================================================
def listar_ingredientes_por_produto(id_produto):
    return listar_itens_receita(id_produto)