from modules.tenant_db import db_conn
from utils.logger import log_info, log_erro
from modules.tenant import get_empresa_id


# =========================================================
# CADASTRAR / ATUALIZAR RECEITA
# =========================================================
def cadastrar_receita(
    id_empresa: int,
    id_produto: int,
    id_materia_prima: int,
    quantidade: float
) -> bool:

    try:
        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT 1
                    FROM receitas
                    WHERE id_produto = %s
                      AND id_materia_prima = %s
                      AND id_empresa = %s
                """, (id_produto, id_materia_prima, id_empresa))

                if cur.fetchone():

                    cur.execute("""
                        UPDATE receitas
                        SET quantidade_utilizada = %s
                        WHERE id_produto = %s
                          AND id_materia_prima = %s
                          AND id_empresa = %s
                    """, (
                        float(quantidade),
                        id_produto,
                        id_materia_prima,
                        id_empresa
                    ))

                else:

                    cur.execute("""
                        INSERT INTO receitas
                        (
                            id_produto,
                            id_materia_prima,
                            quantidade_utilizada,
                            id_empresa
                        )
                        VALUES (%s, %s, %s, %s)
                    """, (
                        id_produto,
                        id_materia_prima,
                        float(quantidade),
                        id_empresa
                    ))

        log_info(
            f"Receita atualizada | Produto {id_produto} | MP {id_materia_prima} | Empresa {id_empresa}"
        )

        return True

    except Exception as e:
        log_erro(f"Erro ao cadastrar receita: {e}")
        return False


# =========================================================
# LISTAR INGREDIENTES
# =========================================================
def listar_itens_receita(id_produto: int) -> list[tuple]:
    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return []

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        mp.id_materia_prima,
                        mp.nome,
                        r.quantidade_utilizada,
                        mp.unidade_medida,
                        mp.preco_unitario
                    FROM receitas r
                    JOIN materia_prima mp
                        ON mp.id_materia_prima = r.id_materia_prima
                       AND mp.id_empresa = r.id_empresa
                    WHERE r.id_produto = %s
                      AND r.id_empresa = %s
                    ORDER BY mp.nome ASC
                """, (id_produto, id_empresa))

                return cur.fetchall()

    except Exception as e:
        log_erro(f"Erro ao listar receita: {e}")
        return []


# =========================================================
# VALIDAR ESTOQUE
# =========================================================
def validar_estoque_suficiente(id_produto: int, quantidade_venda: int) -> bool:
    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return False

        from collections import defaultdict

        consumo_total = defaultdict(float)

        with db_conn() as conn:
            with conn.cursor() as cur:

                # pega toda receita
                cur.execute("""
                    SELECT id_materia_prima, id_subproduto, quantidade_utilizada
                    FROM receitas
                    WHERE id_produto = %s
                      AND id_empresa = %s
                """, (id_produto, id_empresa))

                ingredientes = cur.fetchall()

        from modules.estoque import obter_saldo_materia_prima

        for id_mp, id_sub, qtd_util in ingredientes:

            qtd_necessaria = float(qtd_util) * float(quantidade_venda)

            # ✔ SE FOR MATÉRIA PRIMA DIRETA
            if id_mp is not None:
                consumo_total[id_mp] += qtd_necessaria

            # ❌ SE FOR SUBPRODUTO, IGNORA AQUI
            # (expansão dele deve estar em outra função futura)

        # valida estoque final consolidado
        for id_mp, qtd_total in consumo_total.items():
            saldo = obter_saldo_materia_prima(id_mp)

            print(f"[DEBUG FINAL MP] id={id_mp} saldo={saldo} necessario={qtd_total}")

            if saldo < qtd_total:
                return False

        return True

    except Exception as e:
        log_erro(f"Erro validar estoque: {e}")


# =========================================================
# CUSTO RECEITA
# =========================================================
def calcular_custo_receita(id_produto: int) -> float:
    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return 0.0

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT r.quantidade_utilizada, mp.preco_unitario
                    FROM receitas r
                    JOIN materia_prima mp
                        ON mp.id_materia_prima = r.id_materia_prima
                       AND mp.id_empresa = r.id_empresa
                    WHERE r.id_produto = %s
                      AND r.id_empresa = %s
                """, (id_produto, id_empresa))

                linhas = cur.fetchall()

        return round(
            sum(float(q) * float(p) for q, p in linhas),
            2
        )

    except Exception as e:
        log_erro(f"Erro custo receita: {e}")
        return 0.0


# =========================================================
# ALIAS
# =========================================================
def listar_ingredientes_por_produto(id_produto: int):
    return listar_itens_receita(id_produto)