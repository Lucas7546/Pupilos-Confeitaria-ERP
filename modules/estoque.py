from utils.logger import log_info, log_erro
from modules.tenant import get_empresa_id
from modules.tenant_db import db_conn
from flask import g
 
# =========================================================
# ENTRADA DE ESTOQUE
# =========================================================
def entrada_estoque(
    materia_prima_id: int,
    quantidade: float
) -> bool:

    try:

        id_empresa = get_empresa_id()

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO movimentacao_estoque
                    (
                        id_empresa,
                        id_materia_prima,
                        tipo_movimento,
                        quantidade,
                        observacao
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        'entrada',
                        %s,
                        'Movimentação manual'
                    )
                    """,
                    (
                        id_empresa,
                        materia_prima_id,
                        float(quantidade)
                    ),
                )

        log_info(
            f"Entrada estoque MP {materia_prima_id} | Empresa {id_empresa}"
        )

        return True

    except Exception as e:

        log_erro(f"Erro entrada_estoque: {e}")
        return False
# =========================================================
# SAÍDA DE ESTOQUE
# =========================================================
def saida_estoque(
    materia_prima_id: int,
    quantidade: float,
    observacao: str = "Movimentação manual",
) -> bool:

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO movimentacao_estoque
                    (
                        id_materia_prima,
                        tipo_movimento,
                        quantidade,
                        observacao
                    )
                    VALUES
                    (
                        %s,
                        'saida',
                        %s,
                        %s
                    )
                """, (
                    materia_prima_id,
                    float(quantidade),
                    observacao
                ))

        return True

    except Exception as e:
        log_erro(f"Erro saida_estoque: {e}")
        return False
 
 
# =========================================================
# CALCULAR SALDO ATUAL
# =========================================================
def calcular_estoque(materia_prima_id: int) -> float:

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        COALESCE(
                            SUM(CASE WHEN tipo_movimento IN ('entrada','ajuste') THEN quantidade ELSE 0 END),0)
                        -
                        COALESCE(
                            SUM(CASE WHEN tipo_movimento = 'saida' THEN quantidade ELSE 0 END),0)
                    FROM movimentacao_estoque
                    WHERE id_materia_prima = %s
                """, (materia_prima_id,))

                return float(cur.fetchone()[0] or 0)

    except Exception as e:
        log_erro(f"Erro calcular_estoque: {e}")
        return 0.0
# =========================================================
# LISTAR MATÉRIAS-PRIMAS
# =========================================================
def listar_materia_prima() -> list[tuple]:

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        m.id_materia_prima,
                        m.nome,
                        m.unidade_medida,
                        m.estoque_minimo,
                        m.preco_unitario,

                        COALESCE(
                            SUM(CASE WHEN mov.tipo_movimento IN ('entrada','ajuste') THEN mov.quantidade ELSE 0 END),0)
                        -
                        COALESCE(
                            SUM(CASE WHEN mov.tipo_movimento = 'saida' THEN mov.quantidade ELSE 0 END),0)
                        AS saldo

                    FROM materia_prima m

                    LEFT JOIN movimentacao_estoque mov
                        ON mov.id_materia_prima = m.id_materia_prima

                    GROUP BY
                        m.id_materia_prima,
                        m.nome,
                        m.unidade_medida,
                        m.estoque_minimo,
                        m.preco_unitario

                    ORDER BY m.nome
                """)

                rows = cur.fetchall()

        resultado = []

        for m in rows:

            saldo = float(m[5] or 0)

            status = "BAIXO" if saldo <= float(m[3] or 0) else "OK"

            resultado.append((
                m[0],
                m[1],
                m[2],
                m[3],
                saldo,
                status,
                float(m[4] or 0),
            ))

        return resultado

    except Exception as e:
        log_erro(f"Erro listar_materia_prima: {e}")
        return []
 
# =========================================================
# CADASTRAR MATÉRIA-PRIMA
# =========================================================
def cadastrar_materia(
    nome: str,
    unidade: str,
    preco: float,
    estoque_inicial: float,
    estoque_minimo: float,
) -> bool:

    try:

        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =====================================
                # INSERE MATÉRIA PRIMA
                # =====================================
                cur.execute(
                    """
                    INSERT INTO materia_prima
                    (
                        id_empresa,
                        nome,
                        unidade_medida,
                        preco_unitario,
                        estoque_minimo
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id_materia_prima
                    """,
                    (
                        id_empresa,
                        nome,
                        unidade,
                        preco,
                        estoque_minimo
                    ),
                )

                id_mp = cur.fetchone()[0]

                # =====================================
                # ESTOQUE INICIAL (SE HOUVER)
                # =====================================
                if estoque_inicial and float(estoque_inicial) > 0:

                    cur.execute(
                        """
                        INSERT INTO movimentacao_estoque
                        (
                            id_empresa,
                            id_materia_prima,
                            tipo_movimento,
                            quantidade,
                            observacao
                        )
                        VALUES
                        (
                            %s,
                            %s,
                            'entrada',
                            %s,
                            'Estoque inicial'
                        )
                        """,
                        (
                            id_empresa,
                            id_mp,
                            float(estoque_inicial)
                        ),
                    )

        log_info(
            f"Matéria-prima criada | ID {id_mp} | Empresa {id_empresa}"
        )

        return True

    except Exception as e:

        log_erro(f"Erro cadastrar_materia: {e}")
        return False
 
 
# =========================================================
# REGISTRAR COMPRA (ENTRADA + ATUALIZA PREÇO MÉDIO)
# =========================================================
def registrar_compra_estoque(
    id_materia_prima: int,
    quantidade_comprada,
    valor_total_pago
):
    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            raise Exception("Empresa não definida")

        qtd = float(quantidade_comprada)
        total = float(valor_total_pago)

        if qtd <= 0 or total <= 0:
            log_erro("Tentativa de registro com valor ou qtd zerados/negativos")
            return False

        novo_preco = total / qtd

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT 1
                    FROM materia_prima mp
                    WHERE mp.id_materia_prima = %s
                      AND mp.id_empresa = %s
                """, (id_materia_prima, id_empresa))

                if not cur.fetchone():
                    return False

                cur.execute("""
                    UPDATE materia_prima
                    SET preco_unitario = %s
                    WHERE id_materia_prima = %s
                      AND id_empresa = %s
                """, (
                    novo_preco,
                    id_materia_prima,
                    id_empresa
                ))

                cur.execute("""
                    INSERT INTO movimentacao_estoque
                    (
                        id_empresa,
                        id_materia_prima,
                        tipo_movimento,
                        quantidade,
                        observacao
                    )
                    VALUES
                    (%s, %s, 'entrada', %s, 'Compra registrada')
                """, (
                    id_empresa,
                    id_materia_prima,
                    qtd
                ))

        return True

    except Exception as e:
        log_erro(f"Erro crítico ao processar compra: {e}")
        return False
 
 
# =========================================================
# AJUSTE MANUAL DE ESTOQUE
# =========================================================
def ajustar_estoque(
    id_mp: int,
    novo_valor: float
) -> bool:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT 1
                    FROM materia_prima
                    WHERE id_materia_prima = %s
                      AND id_empresa = %s
                """, (id_mp, id_empresa))

                if not cur.fetchone():
                    return False

                cur.execute("""
                    SELECT
                        COALESCE(
                            SUM(
                                CASE WHEN tipo_movimento IN ('entrada','ajuste')
                                THEN quantidade ELSE 0 END
                            ),0)
                        -
                        COALESCE(
                            SUM(
                                CASE WHEN tipo_movimento = 'saida'
                                THEN quantidade ELSE 0 END
                            ),0)
                    FROM movimentacao_estoque
                    WHERE id_materia_prima = %s
                      AND id_empresa = %s
                """, (id_mp, id_empresa))

                saldo_atual = float(cur.fetchone()[0] or 0)

                diferenca = float(novo_valor) - saldo_atual

                if diferenca == 0:
                    return True

                tipo_movimento = "entrada" if diferenca > 0 else "saida"

                cur.execute("""
                    INSERT INTO movimentacao_estoque
                    (
                        id_empresa,
                        id_materia_prima,
                        tipo_movimento,
                        quantidade,
                        observacao
                    )
                    VALUES (%s, %s, %s, %s, 'Ajuste manual de estoque')
                """, (
                    id_empresa,
                    id_mp,
                    tipo_movimento,
                    abs(diferenca)
                ))

        log_info(f"Ajuste estoque MP {id_mp} | Empresa {id_empresa} | Novo saldo {novo_valor}")

        return True

    except Exception as e:
        log_erro(f"Erro ao ajustar estoque MP {id_mp}: {e}")
        return False
 
# =========================================================
# ATUALIZAR MATÉRIA-PRIMA
# =========================================================
def atualizar_materia_prima(
    id_mp: int,
    nome: str,
    preco: float,
    unidade: str,
    quantidade: float
) -> bool:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =====================================
                # ATUALIZA DADOS BASE
                # =====================================
                cur.execute(
                    """
                    UPDATE materia_prima
                    SET
                        nome = %s,
                        preco_unitario = %s,
                        unidade_medida = %s
                    WHERE id_materia_prima = %s
                      AND id_empresa = %s
                    """,
                    (
                        nome,
                        preco,
                        unidade,
                        id_mp,
                        id_empresa
                    )
                )

                # =====================================
                # CALCULA SALDO ATUAL
                # =====================================
                cur.execute(
                    """
                    SELECT
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN tipo_movimento IN ('entrada','ajuste')
                                    THEN quantidade
                                    ELSE 0
                                END
                            ),0)
                        -
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN tipo_movimento = 'saida'
                                    THEN quantidade
                                    ELSE 0
                                END
                            ),0)
                    FROM movimentacao_estoque
                    WHERE id_materia_prima = %s
                      AND id_empresa = %s
                    """,
                    (id_mp, id_empresa)
                )

                saldo_atual = float(cur.fetchone()[0] or 0)
                novo_saldo = float(quantidade or 0)

                diferenca = novo_saldo - saldo_atual

                # =====================================
                # AJUSTE AUTOMÁTICO DE DIFERENÇA
                # =====================================
                if diferenca != 0:

                    tipo_movimento = "entrada" if diferenca > 0 else "saida"

                    cur.execute(
                        """
                        INSERT INTO movimentacao_estoque
                        (
                            id_empresa,
                            id_materia_prima,
                            tipo_movimento,
                            quantidade,
                            observacao
                        )
                        VALUES
                        (%s, %s, %s, %s, 'Ajuste por edição de matéria-prima')
                        """,
                        (
                            id_empresa,
                            id_mp,
                            tipo_movimento,
                            abs(diferenca)
                        )
                    )

        log_info(f"Matéria-prima ID {id_mp} atualizada.")

        return True

    except Exception as e:
        log_erro(f"Erro ao atualizar matéria-prima ID {id_mp}: {e}")
        return False
 
# =========================================================
# EXCLUIR MATÉRIA-PRIMA
# =========================================================
def excluir_materia_prima(id_mp: int) -> bool:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =====================================
                # REMOVE RECEITAS
                # =====================================
                cur.execute(
                    """
                    DELETE FROM receitas
                    WHERE id_materia_prima = %s
                      AND id_empresa = %s
                    """,
                    (id_mp, id_empresa)
                )

                # =====================================
                # REMOVE MOVIMENTAÇÕES
                # =====================================
                cur.execute(
                    """
                    DELETE FROM movimentacao_estoque
                    WHERE id_materia_prima = %s
                      AND id_empresa = %s
                    """,
                    (id_mp, id_empresa)
                )

                # =====================================
                # REMOVE MATÉRIA-PRIMA
                # =====================================
                cur.execute(
                    """
                    DELETE FROM materia_prima
                    WHERE id_materia_prima = %s
                      AND id_empresa = %s
                    """,
                    (id_mp, id_empresa)
                )

        log_info(f"Matéria-prima ID {id_mp} excluída | Empresa {id_empresa}")

        return True

    except Exception as e:
        log_erro(f"Erro ao excluir matéria-prima ID {id_mp}: {e}")
        return False

# =========================================================
# PREVISÃO DE DEMANDA
# =========================================================
def previsao_demanda() -> list[dict]:
    """Calcula previsão de consumo com base no tenant atual (g.id_empresa)."""

    try:
        id_empresa = getattr(g, "id_empresa", None)

        if not id_empresa:
            raise Exception("Empresa não definida no contexto (g.id_empresa)")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT 
                        mp.nome,
                        mp.unidade_medida,
                        mp.estoque_minimo,
                        COALESCE(saldos.estoque, 0) as estoque_atual,
                        COALESCE(consumo.total_saida, 0) as total_saida
                    FROM materia_prima mp

                    LEFT JOIN (
                        SELECT id_materia_prima, 
                               SUM(
                                   CASE 
                                       WHEN tipo_movimento IN ('entrada','ajuste')
                                       THEN quantidade 
                                       ELSE -quantidade 
                                   END
                               ) as estoque
                        FROM movimentacao_estoque mov
                        WHERE mov.id_empresa = %s
                        GROUP BY id_materia_prima
                    ) saldos ON mp.id_materia_prima = saldos.id_materia_prima

                    LEFT JOIN (
                        SELECT id_materia_prima,
                               SUM(quantidade) as total_saida
                        FROM movimentacao_estoque mov
                        WHERE mov.id_empresa = %s
                          AND tipo_movimento = 'saida'
                          AND data_movimento >= CURRENT_DATE - INTERVAL '30 days'
                        GROUP BY id_materia_prima
                    ) consumo ON mp.id_materia_prima = consumo.id_materia_prima

                    WHERE mp.id_empresa = %s
                """, (id_empresa, id_empresa, id_empresa))

                materias = cur.fetchall()

        previsoes = []

        for nome, unidade, min_est, atual, saida30d in materias:

            media_d = (saida30d or 0) / 30.0
            dias_r = round(atual / media_d, 1) if media_d > 0 else 999.0

            risco = (
                "CRÍTICO" if dias_r <= 2 else
                "ALTO" if dias_r <= 5 else
                "MODERADO" if dias_r <= 10 else
                "BAIXO"
            )

            sugestao = max(round((media_d * 15 * 1.15) - atual, 2), 0.0)

            previsoes.append({
                "materia_prima": nome,
                "unidade": unidade,
                "estoque_atual": round(atual or 0, 2),
                "estoque_minimo": float(min_est or 0),
                "media_diaria": round(media_d, 2),
                "consumo_previsto": round(media_d * 7 * 1.15, 2),
                "dias_restantes": dias_r,
                "risco": risco,
                "sugestao_compra": sugestao
            })

        return sorted(previsoes, key=lambda x: x["dias_restantes"])

    except Exception as e:
        log_erro(f"Erro na previsão: {e}")
        return []
 
# =========================================================
# HISTÓRICO DE MOVIMENTAÇÕES
# =========================================================
def obter_historico_movimentacoes() -> list[dict]:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        mov.id_movimento,
                        mov.data_movimento,
                        COALESCE(mp.nome, s.nome, p.nome) AS nome_item,
                        CASE
                            WHEN mov.id_materia_prima IS NOT NULL THEN 'Matéria-Prima'
                            WHEN mov.id_subproduto IS NOT NULL THEN 'Subproduto'
                            WHEN mov.id_produto IS NOT NULL THEN 'Produto Final'
                            ELSE 'Desconhecido'
                        END AS tipo_item,
                        mov.tipo_movimento,
                        mov.quantidade,
                        COALESCE(
                            mp.unidade_medida,
                            s.unidade_medida,
                            'un'
                        ) AS unidade,
                        mov.observacao
                    FROM movimentacao_estoque mov

                    LEFT JOIN materia_prima mp
                        ON mov.id_materia_prima = mp.id_materia_prima
                        AND mp.id_empresa = mov.id_empresa

                    LEFT JOIN subprodutos s
                        ON mov.id_subproduto = s.id_subproduto
                        AND s.id_empresa = mov.id_empresa

                    LEFT JOIN produtos p
                        ON mov.id_produto = p.id_produto
                        AND p.id_empresa = p.id_empresa

                    WHERE mov.id_empresa = %s

                    ORDER BY
                        mov.data_movimento DESC,
                        mov.id_movimento DESC
                    """,
                    (id_empresa,)
                )

                rows = cur.fetchall()

        return [
            {
                "id": r[0],
                "data": r[1].strftime("%d/%m/%Y %H:%M") if r[1] else "-",
                "item": r[2],
                "tipo_item": r[3],
                "tipo_movimento": (r[4] or "-").upper(),
                "quantidade": float(r[5] or 0),
                "unidade": r[6],
                "observacao": r[7],
            }
            for r in rows
        ]

    except Exception as e:
        log_erro(f"Erro ao obter histórico de movimentações: {e}")
        return []
 
 
# =========================================================
# SUBPRODUTOS — funções que estavam perdidas no app.py
# =========================================================
def listar_subprodutos() -> list[tuple]:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            raise Exception("Empresa não definida")

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        s.id_subproduto,
                        s.nome,
                        s.unidade_medida,
                        COALESCE(s.estoque_minimo, 0),
                        COALESCE(s.preco_custo_unidade, 0.0),

                        COALESCE(
                            SUM(
                                CASE
                                    WHEN mov.tipo_movimento IN ('entrada','ajuste')
                                    THEN mov.quantidade
                                    ELSE 0
                                END
                            ),0
                        )
                        -
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN mov.tipo_movimento = 'saida'
                                    THEN mov.quantidade
                                    ELSE 0
                                END
                            ),0
                        ) AS saldo

                    FROM subprodutos s

                    LEFT JOIN movimentacao_estoque mov
                        ON s.id_subproduto = mov.id_subproduto
                       AND mov.id_empresa = s.id_empresa

                    WHERE
                        s.ativo = 1
                        AND s.id_empresa = %s

                    GROUP BY
                        s.id_subproduto,
                        s.nome,
                        s.unidade_medida,
                        s.estoque_minimo,
                        s.preco_custo_unidade

                    ORDER BY s.nome ASC
                    """,
                    (id_empresa,)
                )

                rows = cur.fetchall()

        resultado = []

        for s in rows:

            estoque_min = float(s[3] or 0)
            saldo = float(s[5] or 0)
            preco = float(s[4] or 0)

            status = "BAIXO" if saldo <= estoque_min else "OK"

            resultado.append(
                (
                    s[0],
                    s[1],
                    s[2],
                    estoque_min,
                    saldo,
                    status,
                    preco
                )
            )

        return resultado

    except Exception as e:
        log_erro(f"Erro ao listar subprodutos: {e}")
        return []
    
def cadastrar_subproduto_banco(
    nome: str,
    unidade: str,
    estoque_minimo: float
) -> bool:

    if not nome or not str(nome).strip():
        return False

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return False

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO subprodutos
                    (
                        id_empresa,
                        nome,
                        unidade_medida,
                        estoque_minimo,
                        ativo
                    )
                    VALUES
                    (%s, %s, %s, %s, 1)
                    """,
                    (
                        id_empresa,
                        nome.strip(),
                        unidade,
                        float(estoque_minimo or 0)
                    )
                )

        return True

    except Exception as e:
        log_erro(f"Erro ao cadastrar subproduto: {e}")
        return False
 
 
def vincular_insumo_subproduto(
    id_subproduto: int,
    id_materia_prima: int,
    quantidade: float
) -> bool:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return False

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT 1
                    FROM subprodutos
                    WHERE id_subproduto = %s
                    AND id_empresa = %s
                """, (id_subproduto, id_empresa))

                if not cur.fetchone():
                    return False

                cur.execute("""
                    SELECT 1
                    FROM materia_prima
                    WHERE id_materia_prima = %s
                    AND id_empresa = %s
                """, (id_materia_prima, id_empresa))

                if not cur.fetchone():
                    return False

                cur.execute("""
                    INSERT INTO receitas_subprodutos
                    (
                        id_empresa,
                        id_subproduto,
                        id_materia_prima,
                        quantidade_utilizada
                    )
                    VALUES (%s, %s, %s, %s)
                """, (
                    id_empresa,
                    id_subproduto,
                    id_materia_prima,
                    float(quantidade)
                ))

        return True

    except Exception as e:
        log_erro(f"Erro ao vincular insumo ao subproduto: {e}")
        return False
 
 
def excluir_subproduto_banco(
    id_subproduto: int
) -> bool:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return False

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    UPDATE subprodutos
                    SET ativo = 0
                    WHERE id_subproduto = %s
                    AND id_empresa = %s
                """, (id_subproduto, id_empresa))

        return True

    except Exception as e:
        log_erro(f"Erro ao desativar subproduto: {e}")
        return False
 
# =========================================================
# ENTRADA DE SUBPRODUTO (chamada em /registrar-producao)
# =========================================================
def entrada_subproduto(
    id_subproduto: int,
    quantidade: float
) -> bool:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return False

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT 1
                    FROM subprodutos
                    WHERE id_subproduto = %s
                    AND id_empresa = %s
                """, (id_subproduto, id_empresa))

                if not cur.fetchone():
                    return False

                cur.execute("""
                    INSERT INTO movimentacao_estoque
                    (
                        id_empresa,
                        id_subproduto,
                        tipo_movimento,
                        quantidade,
                        observacao
                    )
                    VALUES (%s, %s, 'entrada', %s, 'Produção registrada')
                """, (
                    id_empresa,
                    id_subproduto,
                    float(quantidade)
                ))

                cur.execute("""
                    SELECT id_materia_prima, quantidade_utilizada
                    FROM receitas_subprodutos
                    WHERE id_subproduto = %s
                """, (id_subproduto,))

                for id_mp, qtd in cur.fetchall():

                    cur.execute("""
                        INSERT INTO movimentacao_estoque
                        (
                            id_empresa,
                            id_materia_prima,
                            tipo_movimento,
                            quantidade,
                            observacao
                        )
                        VALUES (%s, %s, 'saida', %s, 'Baixa por produção')
                    """, (
                        id_empresa,
                        id_mp,
                        float(qtd) * float(quantidade)
                    ))

        return True

    except Exception as e:
        log_erro(f"Erro entrada_subproduto: {e}")
        return False
 
 
# =========================================================
# ENTRADA DE PRODUTO FINAL (chamada em /registrar-producao)
# =========================================================
def entrada_produto(
    id_produto: int,
    quantidade: float
) -> bool:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return False

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT 1
                    FROM produtos
                    WHERE id_produto = %s
                    AND id_empresa = %s
                """, (id_produto, id_empresa))

                if not cur.fetchone():
                    return False

                cur.execute("""
                    INSERT INTO movimentacao_estoque
                    (
                        id_empresa,
                        id_produto,
                        tipo_movimento,
                        quantidade,
                        observacao
                    )
                    VALUES (%s, %s, 'entrada', %s, 'Produção registrada')
                """, (
                    id_empresa,
                    id_produto,
                    float(quantidade)
                ))

                cur.execute("""
                    SELECT id_materia_prima, quantidade_utilizada
                    FROM receitas
                    WHERE id_produto = %s
                """, (id_produto,))

                for id_mp, qtd in cur.fetchall():

                    cur.execute("""
                        INSERT INTO movimentacao_estoque
                        (
                            id_empresa,
                            id_materia_prima,
                            tipo_movimento,
                            quantidade,
                            observacao
                        )
                        VALUES (%s, %s, 'saida', %s, 'Baixa por produção')
                    """, (
                        id_empresa,
                        id_mp,
                        float(qtd) * float(quantidade)
                    ))

        return True

    except Exception as e:
        log_erro(f"Erro entrada_produto: {e}")
        return False
 
 
# =========================================================
# BALANÇO DIÁRIO (chamada em /estoque/fechamento)
# =========================================================
def obter_balanco_diario() -> list[dict]:
    """
    Retorna fabricado x vendido x sobra de hoje
    para cada produto da empresa.
    """

    try:

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        p.id_produto,
                        p.nome,

                        COALESCE(
                            SUM(
                                CASE
                                    WHEN mov.tipo_movimento = 'entrada'
                                    THEN mov.quantidade
                                    ELSE 0
                                END
                            ),
                            0
                        ) AS fabricado,

                        COALESCE(
                            SUM(iv.quantidade),
                            0
                        ) AS vendido

                    FROM produtos p

                    LEFT JOIN movimentacao_estoque mov
                        ON mov.id_produto = p.id_produto
                        AND DATE(mov.data_movimento) = CURRENT_DATE

                    LEFT JOIN itens_venda iv
                        ON iv.id_produto = p.id_produto

                    LEFT JOIN vendas v
                        ON v.id_venda = iv.id_venda
                        AND DATE(v.data_venda) = CURRENT_DATE

                    GROUP BY
                        p.id_produto,
                        p.nome

                    ORDER BY p.nome ASC
                """)

                rows = cur.fetchall()

        return [
            {
                "id": r[0],
                "nome": r[1],
                "fabricado": float(r[2] or 0),
                "vendido": float(r[3] or 0),
                "sobrou": float(r[2] or 0) - float(r[3] or 0),
            }
            for r in rows
        ]

    except Exception as e:

        log_erro(f"Erro ao obter balanço diário: {e}")
        return []
    

def obter_saldo_produto(id_produto: int) -> float:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return 0.0

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN tipo_movimento IN ('entrada','ajuste')
                                    THEN quantidade
                                    ELSE 0
                                END
                            ),
                            0
                        )
                        -
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN tipo_movimento = 'saida'
                                    THEN quantidade
                                    ELSE 0
                                END
                            ),
                            0
                        )
                    FROM movimentacao_estoque
                    WHERE id_produto = %s
                    AND id_empresa = %s
                    """,
                    (id_produto, id_empresa)
                )

                saldo = cur.fetchone()[0]

        return float(saldo or 0)

    except Exception as e:
        log_erro(
            f"Erro ao consultar saldo produto {id_produto}: {e}"
        )
        return 0.0
    
def obter_saldo_materia_prima(id_mp: int) -> float:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return 0.0

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN tipo_movimento IN ('entrada','ajuste')
                                    THEN quantidade
                                    ELSE 0
                                END
                            ),
                            0
                        )
                        -
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN tipo_movimento = 'saida'
                                    THEN quantidade
                                    ELSE 0
                                END
                            ),
                            0
                        )
                    FROM movimentacao_estoque
                    WHERE id_materia_prima = %s
                    AND id_empresa = %s
                    """,
                    (id_mp, id_empresa)
                )

                saldo = cur.fetchone()[0]

        return float(saldo or 0)

    except Exception as e:

        log_erro(
            f"Erro ao consultar MP {id_mp}: {e}"
        )

        return 0.0
    
def obter_saldo_subproduto(id_subproduto: int) -> float:

    try:
        id_empresa = get_empresa_id()
        if not id_empresa:
            return 0.0

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN tipo_movimento IN ('entrada','ajuste')
                                    THEN quantidade
                                    ELSE 0
                                END
                            ),
                            0
                        )
                        -
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN tipo_movimento = 'saida'
                                    THEN quantidade
                                    ELSE 0
                                END
                            ),
                            0
                        )
                    FROM movimentacao_estoque
                    WHERE id_subproduto = %s
                    AND id_empresa = %s
                    """,
                    (id_subproduto, id_empresa)
                )

                saldo = cur.fetchone()[0]

        return float(saldo or 0)

    except Exception as e:

        log_erro(
            f"Erro ao consultar subproduto {id_subproduto}: {e}"
        )

        return 0.0