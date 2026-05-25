from modules.db import get_conn
from utils.logger import log_info, log_erro


def cadastrar_produto(nome: str, preco_venda: float, categoria: str = "Geral") -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO produtos (nome, preco_venda, categoria) VALUES (%s, %s, %s)",
                    (nome, preco_venda, categoria),
                )
            conn.commit()
        log_info(f"Produto '{nome}' cadastrado.")
        return True
    except Exception as e:
        log_erro(f"Erro ao cadastrar produto '{nome}': {e}")
        return False


def buscar_produto_por_nome(nome: str) -> list[tuple]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_produto, nome, preco_venda, categoria
                    FROM produtos
                    WHERE nome ILIKE %s AND ativo = 1
                    ORDER BY nome ASC
                    """,
                    (f"%{nome}%",),
                )
                return cur.fetchall()
    except Exception as e:
        log_erro(f"Erro ao buscar produto '{nome}': {e}")
        return []


def listar_todos() -> list[tuple]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id_produto, nome, preco_venda, categoria FROM produtos ORDER BY nome ASC"
                )
                return cur.fetchall()
    except Exception as e:
        log_erro(f"Erro ao listar produtos: {e}")
        return []


def vincular_insumo(id_produto: int, id_materia: int, quantidade: float) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id_receita FROM receitas WHERE id_produto = %s AND id_materia_prima = %s",
                    (id_produto, id_materia),
                )
                existe = cur.fetchone()
                if existe:
                    cur.execute(
                        "UPDATE receitas SET quantidade_utilizada = %s WHERE id_receita = %s",
                        (quantidade, existe[0]),
                    )
                else:
                    cur.execute(
                        "INSERT INTO receitas (id_produto, id_materia_prima, quantidade_utilizada) VALUES (%s,%s,%s)",
                        (id_produto, id_materia, quantidade),
                    )
            conn.commit()
        return True
    except Exception as e:
        log_erro(f"Erro ao vincular insumo (Prod: {id_produto}, MP: {id_materia}): {e}")
        return False


def vincular_subproduto_ao_produto(id_produto: int, id_subproduto: int, quantidade: float) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id_receita FROM receitas WHERE id_produto = %s AND id_subproduto = %s",
                    (id_produto, id_subproduto),
                )
                existe = cur.fetchone()
                if existe:
                    cur.execute(
                        "UPDATE receitas SET quantidade_utilizada = %s WHERE id_receita = %s",
                        (quantidade, existe[0]),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO receitas (id_produto, id_subproduto, id_materia_prima, quantidade_utilizada)
                        VALUES (%s, %s, NULL, %s)
                        """,
                        (id_produto, id_subproduto, quantidade),
                    )
            conn.commit()
        return True
    except Exception as e:
        log_erro(f"Erro ao vincular subproduto {id_subproduto} ao produto {id_produto}: {e}")
        return False


def calcular_cenarios_preco(id_produto: int, preco_venda_atual: float) -> dict:
    from modules.receitas import calcular_custo_receita

    try:
        custo_base = calcular_custo_receita(id_produto)
        if not custo_base:
            return {"atual": preco_venda_atual, "ponto_equilibrio": 0, "lucro_30": 0, "custo_real": 0}
        return {
            "atual": preco_venda_atual,
            "ponto_equilibrio": round(custo_base * 1.10, 2),
            "lucro_30": round(custo_base / 0.70, 2),
            "custo_real": round(custo_base, 2),
        }
    except Exception as e:
        log_erro(f"Erro ao calcular cenários de preço ID {id_produto}: {e}")
        return {}


# =========================================================
# CAPACIDADE GERAL DE PRODUÇÃO
# Bug corrigido: a versão anterior abria uma nova conexão por produto
# (N+1 queries). Agora carrega todas as receitas e o saldo de
# todas as MPs em dois queries e resolve na memória.
# =========================================================
def calcular_capacidade_geral() -> list[dict]:
    from modules.estoque import calcular_estoque  # local para evitar circular

    try:
        produtos_lista = buscar_produto_por_nome("")
        if not produtos_lista:
            return []

        ids_produtos = [p[0] for p in produtos_lista]

        with get_conn() as conn:
            with conn.cursor() as cur:
                # Todas as receitas dos produtos ativos de uma vez
                cur.execute(
                    """
                    SELECT id_produto, id_materia_prima, quantidade_utilizada
                    FROM receitas
                    WHERE id_produto = ANY(%s) AND id_materia_prima IS NOT NULL
                    """,
                    (ids_produtos,),
                )
                receitas = cur.fetchall()

                # Todos os saldos de MPs usadas
                ids_mps = list({r[1] for r in receitas})
                saldos: dict[int, float] = {}
                if ids_mps:
                    cur.execute(
                        """
                        SELECT id_materia_prima,
                            COALESCE(SUM(CASE WHEN tipo_movimento IN ('entrada','ajuste')
                                             THEN quantidade ELSE 0 END), 0)
                            - COALESCE(SUM(CASE WHEN tipo_movimento = 'saida'
                                               THEN quantidade ELSE 0 END), 0)
                        FROM movimentacao_estoque
                        WHERE id_materia_prima = ANY(%s)
                        GROUP BY id_materia_prima
                        """,
                        (ids_mps,),
                    )
                    saldos = {row[0]: float(row[1]) for row in cur.fetchall()}

        # Agrupa receitas por produto
        receitas_por_produto: dict[int, list[tuple]] = {}
        for id_p, id_mp, qtd in receitas:
            receitas_por_produto.setdefault(id_p, []).append((id_mp, qtd))

        resultado = []
        for p in produtos_lista:
            id_p, nome_p = p[0], p[1]
            ingredientes = receitas_por_produto.get(id_p, [])
            if not ingredientes:
                continue
            limites = []
            for id_mp, qtd_necessaria in ingredientes:
                if qtd_necessaria and float(qtd_necessaria) > 0:
                    saldo = saldos.get(id_mp, 0.0)
                    limites.append(saldo // float(qtd_necessaria))
            if limites:
                resultado.append({"nome": nome_p, "qtd": int(min(limites))})

        return resultado
    except Exception as e:
        log_erro(f"Erro ao calcular capacidade geral: {e}")
        return []


def excluir_produto(id_produto: int) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM receitas WHERE id_produto = %s", (id_produto,))
                cur.execute("DELETE FROM itens_venda WHERE id_produto = %s", (id_produto,))
                cur.execute("DELETE FROM produtos WHERE id_produto = %s", (id_produto,))
            conn.commit()
        log_info(f"Produto {id_produto} excluído.")
        return True
    except Exception as e:
        log_erro(f"Erro ao excluir produto {id_produto}: {e}")
        return False


def update_produto(id_produto: int, nome: str, preco: float) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE produtos SET nome = %s, preco_venda = %s WHERE id_produto = %s",
                    (nome, preco, id_produto),
                )
            conn.commit()
        log_info(f"Produto ID {id_produto} atualizado.")
        return True
    except Exception as e:
        log_erro(f"Erro ao atualizar produto ID {id_produto}: {e}")
        return False
