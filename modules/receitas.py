from modules.db import get_conn
from utils.logger import log_info, log_erro


# =========================================================
# CADASTRAR / ATUALIZAR RECEITA
# =========================================================
def cadastrar_receita(id_produto: int, id_materia_prima: int, quantidade: float) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM receitas WHERE id_produto = %s AND id_materia_prima = %s",
                    (id_produto, id_materia_prima),
                )
                if cur.fetchone():
                    cur.execute(
                        """
                        UPDATE receitas SET quantidade_utilizada = %s
                        WHERE id_produto = %s AND id_materia_prima = %s
                        """,
                        (float(quantidade), id_produto, id_materia_prima),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO receitas (id_produto, id_materia_prima, quantidade_utilizada)
                        VALUES (%s, %s, %s)
                        """,
                        (id_produto, id_materia_prima, float(quantidade)),
                    )
            conn.commit()
        log_info(f"Receita: Produto {id_produto}, MP {id_materia_prima}, Qtd: {quantidade}")
        return True
    except Exception as e:
        log_erro(f"Erro ao cadastrar receita (Prod: {id_produto}, MP: {id_materia_prima}): {e}")
        return False


# =========================================================
# LISTAR INGREDIENTES DE UM PRODUTO
# =========================================================
def listar_itens_receita(id_produto: int) -> list[tuple]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT mp.id_materia_prima, mp.nome, r.quantidade_utilizada,
                           mp.unidade_medida, mp.preco_unitario
                    FROM receitas r
                    JOIN materia_prima mp ON mp.id_materia_prima = r.id_materia_prima
                    WHERE r.id_produto = %s
                    ORDER BY mp.nome ASC
                    """,
                    (id_produto,),
                )
                return cur.fetchall()
    except Exception as e:
        log_erro(f"Erro ao listar itens da receita (Prod: {id_produto}): {e}")
        return []


# =========================================================
# VALIDAR ESTOQUE ANTES DA VENDA
# Import corrigido: calcular_estoque vem de estoque mas
# o import é feito dentro da função para evitar circular import
# (estoque → receitas → estoque).
# =========================================================
def validar_estoque_suficiente(id_produto: int, quantidade_venda: int) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id_materia_prima, quantidade_utilizada FROM receitas WHERE id_produto = %s",
                    (id_produto,),
                )
                ingredientes = cur.fetchall()

        if not ingredientes:
            return True

        # Import local para quebrar o ciclo receitas ↔ estoque
        from modules.estoque import calcular_estoque

        for id_mp, qtd_necessaria in ingredientes:
            estoque_atual = calcular_estoque(id_mp)
            if estoque_atual < float(qtd_necessaria) * float(quantidade_venda):
                return False

        return True
    except Exception as e:
        log_erro(f"Erro ao validar estoque (Prod: {id_produto}): {e}")
        return False


# =========================================================
# CALCULAR CUSTO TOTAL DA RECEITA
# =========================================================
def calcular_custo_receita(id_produto: int) -> float:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.quantidade_utilizada, mp.preco_unitario
                    FROM receitas r
                    JOIN materia_prima mp ON mp.id_materia_prima = r.id_materia_prima
                    WHERE r.id_produto = %s
                    """,
                    (id_produto,),
                )
                linhas = cur.fetchall()

        return round(sum(float(qtd or 0) * float(preco or 0) for qtd, preco in linhas), 2)
    except Exception as e:
        log_erro(f"Erro ao calcular custo da receita (Prod: {id_produto}): {e}")
        return 0.0


# Alias de compatibilidade
def listar_ingredientes_por_produto(id_produto: int) -> list[tuple]:
    return listar_itens_receita(id_produto)
