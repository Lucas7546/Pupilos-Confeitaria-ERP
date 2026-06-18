from modules.tenant_db import db_conn
from utils.logger import log_info, log_erro
from flask_login import current_user
from modules.tenant import get_empresa_id
import traceback

def cadastrar_produto(
    nome: str,
    preco_venda: float,
    categoria: str = "Geral"
) -> bool:

    try:
        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO produtos
                    (
                        nome,
                        preco_venda,
                        categoria,
                        id_empresa
                    )
                    VALUES (%s, %s, %s, %s)
                """, (
                    nome,
                    preco_venda,
                    categoria,
                    id_empresa
                ))

        log_info(f"Produto '{nome}' cadastrado. Empresa {id_empresa}")
        return True

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao cadastrar produto '{nome}': {erro_detalhado}")
        traceback.print_exc()
        return False


def buscar_produto_por_nome(nome: str) -> list[tuple]:

    try:
        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        id_produto,
                        nome,
                        preco_venda,
                        categoria
                    FROM produtos
                    WHERE nome ILIKE %s
                    AND ativo = 1
                    AND id_empresa = %s
                    ORDER BY nome ASC
                """, (
                    f"%{nome}%",
                    id_empresa
                ))

                return cur.fetchall()

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao buscar produto '{nome}': {erro_detalhado}")
        traceback.print_exc()
        return []


def listar_todos() -> list[tuple]:

    try:
        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        id_produto,
                        nome,
                        preco_venda,
                        categoria
                    FROM produtos
                    WHERE id_empresa = %s
                    ORDER BY nome ASC
                """, (id_empresa,))

                return cur.fetchall()

    except Exception as e:
        log_erro(f"Erro ao listar produtos: {e}")
        return []


def vincular_insumo(
    id_produto: int,
    id_materia: int,
    quantidade: float
) -> bool:

    try:
        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT id_receita
                    FROM receitas
                    WHERE id_produto = %s
                    AND id_materia_prima = %s
                    AND id_empresa = %s
                """, (
                    id_produto,
                    id_materia,
                    id_empresa
                ))

                existe = cur.fetchone()

                if existe:

                    cur.execute("""
                        UPDATE receitas
                        SET quantidade_utilizada = %s
                        WHERE id_receita = %s
                        AND id_empresa = %s
                    """, (
                        float(quantidade),
                        existe[0],
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
                        id_materia,
                        float(quantidade),
                        id_empresa
                    ))

        return True

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao vincular insumo (Prod: {id_produto}, MP: {id_materia}): {erro_detalhado}")
        traceback.print_exc()
        return False

def vincular_subproduto_ao_produto(
    id_produto: int,
    id_subproduto: int,
    quantidade: float
) -> bool:

    try:
        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT id_receita
                    FROM receitas
                    WHERE id_produto = %s
                    AND id_subproduto = %s
                    AND id_empresa = %s
                """, (
                    id_produto,
                    id_subproduto,
                    id_empresa
                ))

                existe = cur.fetchone()

                if existe:

                    cur.execute("""
                        UPDATE receitas
                        SET quantidade_utilizada = %s
                        WHERE id_receita = %s
                        AND id_empresa = %s
                    """, (
                        float(quantidade),
                        existe[0],
                        id_empresa
                    ))

                else:

                    cur.execute("""
                        INSERT INTO receitas
                        (
                            id_produto,
                            id_subproduto,
                            quantidade_utilizada,
                            id_empresa
                        )
                        VALUES (%s, %s, %s, %s)
                    """, (
                        id_produto,
                        id_subproduto,
                        float(quantidade),
                        id_empresa
                    ))

        return True

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao vincular subproduto {id_subproduto} ao produto {id_produto}: {erro_detalhado}")
        traceback.print_exc()
        return False

def calcular_cenarios_preco(
    id_produto: int,
    preco_venda_atual: float
) -> dict:

    from modules.receitas import calcular_custo_receita

    try:

        custo_base = calcular_custo_receita(id_produto)

        if custo_base <= 0:
            return {
                "atual": float(preco_venda_atual),
                "ponto_equilibrio": 0.0,
                "preco_margem_30": 0.0,
                "custo_real": 0.0
            }

        margem_30 = custo_base / 0.70  # margem de 30%

        return {
            "atual": float(preco_venda_atual),

            # break-even simples (custo puro)
            "ponto_equilibrio": round(custo_base, 2),

            # preço para margem de 30%
            "preco_margem_30": round(margem_30, 2),

            "custo_real": round(custo_base, 2),
        }

    except Exception as e:
        erro_detalhado = traceback.format_exc()

        log_erro(f"Erro ao calcular cenários de preço ID {id_produto}: {erro_detalhado}")
        traceback.print_exc()
        return {}


# =========================================================
# CAPACIDADE GERAL DE PRODUÇÃO
# =========================================================
def calcular_capacidade_geral():
    try:

        id_empresa = current_user.id_empresa

        if not id_empresa:
            return []

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =========================
                # PRODUTOS
                # =========================
                cur.execute("""
                    SELECT id_produto, nome
                    FROM produtos
                    WHERE id_empresa = %s
                    AND ativo = 1
                """, (id_empresa,))

                produtos_lista = cur.fetchall()

                if not produtos_lista:
                    return []

                ids_produtos = [p[0] for p in produtos_lista]

                # =========================
                # RECEITAS
                # =========================
                cur.execute("""
                    SELECT id_produto, id_materia_prima, quantidade_utilizada
                    FROM receitas
                    WHERE id_produto = ANY(%s)
                    AND id_empresa = %s
                    AND id_materia_prima IS NOT NULL
                """, (ids_produtos, id_empresa))

                receitas = cur.fetchall()

                ids_mps = list({r[1] for r in receitas if r[1]})

                # =========================
                # SALDOS MP
                # =========================
                saldos = {}

                if ids_mps:

                    cur.execute("""
                        SELECT
                            id_materia_prima,
                            COALESCE(SUM(
                                CASE
                                    WHEN tipo_movimento IN ('entrada','ajuste') THEN quantidade
                                    ELSE 0
                                END
                            ),0)
                            -
                            COALESCE(SUM(
                                CASE
                                    WHEN tipo_movimento = 'saida' THEN quantidade
                                    ELSE 0
                                END
                            ),0)
                        FROM movimentacao_estoque
                        WHERE id_materia_prima = ANY(%s)
                        AND id_empresa = %s
                        GROUP BY id_materia_prima
                    """, (ids_mps, id_empresa))

                    saldos = {r[0]: float(r[1]) for r in cur.fetchall()}

        # =========================
        # AGRUPA RECEITAS
        # =========================
        receitas_por_produto = {}

        for id_produto, id_mp, qtd in receitas:
            receitas_por_produto.setdefault(id_produto, []).append((id_mp, float(qtd)))

        # =========================
        # CÁLCULO FINAL
        # =========================
        resultado = []

        for id_produto, nome in produtos_lista:

            ingredientes = receitas_por_produto.get(id_produto, [])

            if not ingredientes:
                continue

            limites = []

            for id_mp, qtd in ingredientes:

                if not qtd or qtd <= 0:
                    continue

                saldo = saldos.get(id_mp, 0.0)

                limites.append(saldo / qtd)

            if limites:

                resultado.append({
                    "nome": nome,
                    "qtd": int(min(limites))
                })

        return resultado

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao calcular capacidade geral: {erro_detalhado}")
        traceback.print_exc()
        return []


def excluir_produto(id_produto: int) -> bool:

    try:

        id_empresa = current_user.id_empresa

        with db_conn() as conn:
            with conn.cursor() as cur:

                # desativa produto
                cur.execute("""
                    UPDATE produtos
                    SET ativo = 0
                    WHERE id_produto = %s
                    AND id_empresa = %s
                """, (id_produto, id_empresa))

                # remove receita (opcional)
                cur.execute("""
                    DELETE FROM receitas
                    WHERE id_produto = %s
                    AND id_empresa = %s
                """, (id_produto, id_empresa))

        log_info(f"Produto {id_produto} desativado. Empresa {id_empresa}")

        return True

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao excluir produto {id_produto}: {erro_detalhado}")
        traceback.print_exc()
        return False


def update_produto(
    id_produto: int,
    nome: str,
    preco: float
) -> bool:

    try:

        id_empresa = current_user.id_empresa

        if not nome or preco <= 0:
            return False

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    UPDATE produtos
                    SET nome = %s,
                        preco_venda = %s
                    WHERE id_produto = %s
                    AND id_empresa = %s
                """, (
                    nome.strip(),
                    float(preco),
                    id_produto,
                    id_empresa
                ))

        log_info(f"Produto ID {id_produto} atualizado.")

        return True

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao atualizar produto ID {id_produto}: {erro_detalhado}")
        traceback.print_exc()
        return False
