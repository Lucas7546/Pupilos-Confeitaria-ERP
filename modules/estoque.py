
from datetime import datetime, timedelta  # timedelta estava faltando
 
from modules.db import get_conn
from utils.logger import log_info, log_erro
 
 
# =========================================================
# ENTRADA DE ESTOQUE
# =========================================================
def entrada_estoque(materia_prima_id: int, quantidade: float) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO movimentacao_estoque
                        (id_materia_prima, tipo_movimento, quantidade, observacao)
                    VALUES (%s, 'entrada', %s, 'Movimentação manual')
                    """,
                    (materia_prima_id, float(quantidade)),
                )
            conn.commit()
        log_info(f"Entrada estoque MP {materia_prima_id} | Qtd: {quantidade}")
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
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO movimentacao_estoque
                        (id_materia_prima, tipo_movimento, quantidade, observacao)
                    VALUES (%s, 'saida', %s, %s)
                    """,
                    (materia_prima_id, float(quantidade), observacao),
                )
            conn.commit()
        log_info(f"Saída estoque MP {materia_prima_id} | Qtd: {quantidade}")
        return True
    except Exception as e:
        log_erro(f"Erro saida_estoque: {e}")
        return False
 
 
# =========================================================
# CALCULAR SALDO ATUAL
# =========================================================
def calcular_estoque(materia_prima_id: int) -> float:
    """Retorna o saldo atual de uma matéria-prima calculado pela movimentação."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN tipo_movimento IN ('entrada','ajuste')
                                         THEN quantidade ELSE 0 END), 0)
                        -
                        COALESCE(SUM(CASE WHEN tipo_movimento = 'saida'
                                         THEN quantidade ELSE 0 END), 0)
                    FROM movimentacao_estoque
                    WHERE id_materia_prima = %s
                    """,
                    (materia_prima_id,),
                )
                return float(cur.fetchone()[0] or 0)
    except Exception as e:
        log_erro(f"Erro calcular_estoque: {e}")
        return 0.0
 
 
# =========================================================
# LISTAR MATÉRIAS-PRIMAS
# =========================================================
def listar_materia_prima() -> list[tuple]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        m.id_materia_prima,
                        m.nome,
                        m.unidade_medida,
                        m.estoque_minimo,
                        m.preco_unitario,
                        COALESCE(SUM(CASE WHEN mov.tipo_movimento IN ('entrada','ajuste')
                                         THEN mov.quantidade ELSE 0 END), 0)
                        - COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'saida'
                                           THEN mov.quantidade ELSE 0 END), 0) AS saldo
                    FROM materia_prima m
                    LEFT JOIN movimentacao_estoque mov
                        ON m.id_materia_prima = mov.id_materia_prima
                    GROUP BY
                        m.id_materia_prima, m.nome, m.unidade_medida,
                        m.estoque_minimo, m.preco_unitario
                    ORDER BY m.nome ASC
                    """
                )
                rows = cur.fetchall()
 
        resultado = []
        for m in rows:
            saldo = float(m[5])
            status = "BAIXO" if saldo <= float(m[3] or 0) else "OK"
            resultado.append((m[0], m[1], m[2], m[3], saldo, status, float(m[4] or 0)))
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
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO materia_prima
                        (nome, unidade_medida, preco_unitario, estoque_minimo)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id_materia_prima
                    """,
                    (nome, unidade, preco, estoque_minimo),
                )
                id_mp = cur.fetchone()[0]
 
                if estoque_inicial > 0:
                    cur.execute(
                        """
                        INSERT INTO movimentacao_estoque
                            (id_materia_prima, tipo_movimento, quantidade, observacao)
                        VALUES (%s, 'entrada', %s, 'Estoque inicial')
                        """,
                        (id_mp, estoque_inicial),
                    )
            conn.commit()
        log_info(f"Matéria-prima cadastrada: {nome} (ID: {id_mp})")
        return True
    except Exception as e:
        log_erro(f"Erro ao cadastrar matéria-prima '{nome}': {e}")
        return False
 
 
# =========================================================
# REGISTRAR COMPRA (ENTRADA + ATUALIZA PREÇO MÉDIO)
# =========================================================
def registrar_compra_estoque(
    id_materia_prima: int,
    quantidade_comprada: float,
    valor_total_pago: float,
) -> bool:
    if quantidade_comprada <= 0:
        return False
    try:
        novo_preco = float(valor_total_pago) / float(quantidade_comprada)
        data_str = datetime.now().strftime("%d/%m/%Y")
 
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE materia_prima SET preco_unitario = %s WHERE id_materia_prima = %s",
                    (novo_preco, id_materia_prima),
                )
                cur.execute(
                    """
                    INSERT INTO movimentacao_estoque
                        (id_materia_prima, tipo_movimento, quantidade, observacao)
                    VALUES (%s, 'entrada', %s, %s)
                    """,
                    (id_materia_prima, float(quantidade_comprada), f"Compra em {data_str}"),
                )
            conn.commit()
        log_info(f"Compra registrada. ID MP: {id_materia_prima}, Qtd: {quantidade_comprada}")
        return True
    except Exception as e:
        log_erro(f"Erro ao registrar compra (ID MP: {id_materia_prima}): {e}")
        return False
 
 
# =========================================================
# AJUSTE MANUAL DE ESTOQUE
# Bug corrigido: agora retorna bool para o chamador saber se teve sucesso.
# =========================================================
def ajustar_estoque(id_mp: int, novo_valor: float) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO movimentacao_estoque
                        (id_materia_prima, tipo_movimento, quantidade, observacao)
                    VALUES (%s, 'ajuste', %s, 'Ajuste manual de estoque')
                    """,
                    (id_mp, float(novo_valor)),
                )
            conn.commit()
        log_info(f"Ajuste manual. ID MP: {id_mp}, Quantidade: {novo_valor}")
        return True
    except Exception as e:
        log_erro(f"Erro ao ajustar estoque (ID MP: {id_mp}): {e}")
        return False
 
 
# =========================================================
# ATUALIZAR MATÉRIA-PRIMA
# =========================================================
def atualizar_materia_prima(
    id_mp: int, nome: str, preco: float, unidade: str, quantidade: float
) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE materia_prima
                    SET nome = %s, preco_unitario = %s, unidade_medida = %s
                    WHERE id_materia_prima = %s
                    """,
                    (nome, preco, unidade, id_mp),
                )
                if quantidade and float(quantidade) > 0:
                    cur.execute(
                        """
                        INSERT INTO movimentacao_estoque
                            (id_materia_prima, tipo_movimento, quantidade, observacao)
                        VALUES (%s, 'entrada', %s, 'Ajuste manual de estoque')
                        """,
                        (id_mp, quantidade),
                    )
            conn.commit()
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
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM receitas WHERE id_materia_prima = %s", (id_mp,))
                cur.execute(
                    "DELETE FROM movimentacao_estoque WHERE id_materia_prima = %s", (id_mp,)
                )
                cur.execute("DELETE FROM materia_prima WHERE id_materia_prima = %s", (id_mp,))
            conn.commit()
        log_info(f"Matéria-prima ID {id_mp} excluída.")
        return True
    except Exception as e:
        log_erro(f"Erro ao excluir matéria-prima ID {id_mp}: {e}")
        return False
 
 
# =========================================================
# PREVISÃO DE DEMANDA
# Consolidada aqui — previsao.py será depreciado.
# A lógica em app.py (rota /previsao-estoque) deve chamar esta função.
# =========================================================
def previsao_demanda() -> list[dict]:
    """
    Calcula previsão de consumo para todas as matérias-primas com base
    nos últimos 30 dias de movimentação de saída.
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_materia_prima, nome, unidade_medida, estoque_minimo
                    FROM materia_prima
                    ORDER BY nome ASC
                    """
                )
                materias = cur.fetchall()
 
                previsoes: list[dict] = []
                for id_mp, nome, unidade, estoque_minimo in materias:
                    estoque_minimo = float(estoque_minimo or 0)
 
                    # Saldo atual
                    cur.execute(
                        """
                        SELECT
                            COALESCE(SUM(CASE WHEN tipo_movimento IN ('entrada','ajuste')
                                             THEN quantidade ELSE 0 END), 0)
                            - COALESCE(SUM(CASE WHEN tipo_movimento = 'saida'
                                               THEN quantidade ELSE 0 END), 0)
                        FROM movimentacao_estoque
                        WHERE id_materia_prima = %s
                        """,
                        (id_mp,),
                    )
                    estoque_atual = float(cur.fetchone()[0] or 0)
 
                    # Consumo últimos 30 dias
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(quantidade), 0)
                        FROM movimentacao_estoque
                        WHERE id_materia_prima = %s
                          AND tipo_movimento = 'saida'
                          AND data_movimento >= CURRENT_DATE - INTERVAL '30 days'
                        """,
                        (id_mp,),
                    )
                    total_consumido = float(cur.fetchone()[0] or 0)
 
                    media_diaria = total_consumido / 30.0
                    fator = 1.15
 
                    consumo_7d = round(media_diaria * 7 * fator, 2)
                    consumo_15d = round(media_diaria * 15 * fator, 2)
                    dias_restantes = (
                        round(estoque_atual / media_diaria, 1) if media_diaria > 0 else 999.0
                    )
 
                    if dias_restantes <= 2:
                        risco = "CRÍTICO"
                    elif dias_restantes <= 5:
                        risco = "ALTO"
                    elif dias_restantes <= 10:
                        risco = "MODERADO"
                    else:
                        risco = "BAIXO"
 
                    sugestao = max(round(consumo_15d - estoque_atual, 2), 0.0)
 
                    previsoes.append(
                        {
                            "materia_prima": nome,
                            "unidade": unidade,
                            "estoque_atual": round(estoque_atual, 2),
                            "media_diaria": round(media_diaria, 2),
                            "consumo_previsto": consumo_7d,
                            "consumo_15d": consumo_15d,
                            "dias_restantes": dias_restantes,
                            "risco": risco,
                            "sugestao_compra": sugestao,
                        }
                    )
 
        previsoes.sort(key=lambda x: x["dias_restantes"])
        return previsoes
    except Exception as e:
        log_erro(f"Erro na previsão de demanda: {e}")
        return []
 
 
# =========================================================
# HISTÓRICO DE MOVIMENTAÇÕES
# =========================================================
def obter_historico_movimentacoes() -> list[dict]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        mov.id_movimentacao,
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
                        COALESCE(mp.unidade_medida, s.unidade_medida, 'un') AS unidade,
                        mov.observacao
                    FROM movimentacao_estoque mov
                    LEFT JOIN materia_prima mp ON mov.id_materia_prima = mp.id_materia_prima
                    LEFT JOIN subprodutos s ON mov.id_subproduto = s.id_subproduto
                    LEFT JOIN produtos p ON mov.id_produto = p.id_produto
                    ORDER BY mov.data_movimento DESC, mov.id_movimentacao DESC
                    """
                )
                rows = cur.fetchall()
 
        return [
            {
                "id": r[0],
                "data": r[1].strftime("%d/%m/%Y %H:%M") if r[1] else "-",
                "item": r[2],
                "tipo_item": r[3],
                "tipo_movimento": r[4].upper() if r[4] else "-",
                "quantidade": float(r[5]),
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
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        s.id_subproduto,
                        s.nome,
                        s.unidade_medida,
                        COALESCE(s.estoque_minimo, 0),
                        COALESCE(s.preco_custo_unidade, 0.0),
                        COALESCE(SUM(CASE WHEN mov.tipo_movimento IN ('entrada','ajuste')
                                         THEN mov.quantidade ELSE 0 END), 0)
                        - COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'saida'
                                           THEN mov.quantidade ELSE 0 END), 0) AS saldo
                    FROM subprodutos s
                    LEFT JOIN movimentacao_estoque mov ON s.id_subproduto = mov.id_subproduto
                    WHERE s.ativo = 1
                    GROUP BY s.id_subproduto, s.nome, s.unidade_medida,
                             s.estoque_minimo, s.preco_custo_unidade
                    ORDER BY s.nome ASC
                    """
                )
                rows = cur.fetchall()
 
        resultado = []
        for s in rows:
            estoque_min = float(s[3] or 0)
            saldo = float(s[5] or 0)
            preco = float(s[4] or 0)
            status = "BAIXO" if saldo <= estoque_min else "OK"
            resultado.append((s[0], s[1], s[2], estoque_min, saldo, status, preco))
        return resultado
    except Exception as e:
        log_erro(f"Erro ao listar subprodutos: {e}")
        return []
 
 
def cadastrar_subproduto_banco(nome: str, unidade: str, estoque_minimo: float) -> bool:
    if not nome or not str(nome).strip():
        return False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO subprodutos (nome, unidade_medida, estoque_minimo, ativo)
                    VALUES (%s, %s, %s, 1)
                    """,
                    (nome.strip(), unidade, float(estoque_minimo or 0)),
                )
            conn.commit()
        return True
    except Exception as e:
        log_erro(f"Erro ao cadastrar subproduto: {e}")
        return False
 
 
def vincular_insumo_subproduto(
    id_subproduto: int, id_materia_prima: int, quantidade: float
) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO receitas_subprodutos
                        (id_subproduto, id_materia_prima, quantidade_utilizada)
                    VALUES (%s, %s, %s)
                    """,
                    (int(id_subproduto), int(id_materia_prima), float(quantidade)),
                )
            conn.commit()
        return True
    except Exception as e:
        log_erro(f"Erro ao vincular insumo ao subproduto: {e}")
        return False
 
 
def excluir_subproduto_banco(id_subproduto: int) -> bool:
    """Soft delete — mantém histórico fiscal."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE subprodutos SET ativo = 0 WHERE id_subproduto = %s",
                    (int(id_subproduto),),
                )
            conn.commit()
        return True
    except Exception as e:
        log_erro(f"Erro ao desativar subproduto: {e}")
        return False
 
 
# =========================================================
# ENTRADA DE SUBPRODUTO (chamada em /registrar-producao)
# =========================================================
def entrada_subproduto(id_subproduto: int, quantidade: float) -> bool:
    """Registra entrada de subproduto produzido e baixa os insumos da receita."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Entrada no estoque do subproduto
                cur.execute(
                    """
                    INSERT INTO movimentacao_estoque
                        (id_subproduto, tipo_movimento, quantidade, observacao)
                    VALUES (%s, 'entrada', %s, 'Produção registrada')
                    """,
                    (id_subproduto, float(quantidade)),
                )
                # Baixa os insumos usados na receita do subproduto
                cur.execute(
                    "SELECT id_materia_prima, quantidade_utilizada FROM receitas_subprodutos WHERE id_subproduto = %s",
                    (id_subproduto,),
                )
                for id_mp, qtd_receita in cur.fetchall():
                    cur.execute(
                        """
                        INSERT INTO movimentacao_estoque
                            (id_materia_prima, tipo_movimento, quantidade, observacao)
                        VALUES (%s, 'saida', %s, 'Baixa por produção de subproduto')
                        """,
                        (id_mp, float(qtd_receita) * float(quantidade)),
                    )
            conn.commit()
        log_info(f"Entrada subproduto ID {id_subproduto} | Qtd {quantidade}")
        return True
    except Exception as e:
        log_erro(f"Erro entrada_subproduto ID {id_subproduto}: {e}")
        return False
 
 
# =========================================================
# ENTRADA DE PRODUTO FINAL (chamada em /registrar-producao)
# =========================================================
def entrada_produto(id_produto: int, quantidade: float) -> bool:
    """Registra entrada de produto final produzido e baixa os insumos da receita."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO movimentacao_estoque
                        (id_produto, tipo_movimento, quantidade, observacao)
                    VALUES (%s, 'entrada', %s, 'Produção registrada')
                    """,
                    (id_produto, float(quantidade)),
                )
                cur.execute(
                    "SELECT id_materia_prima, quantidade_utilizada FROM receitas WHERE id_produto = %s AND id_materia_prima IS NOT NULL",
                    (id_produto,),
                )
                for id_mp, qtd_receita in cur.fetchall():
                    cur.execute(
                        """
                        INSERT INTO movimentacao_estoque
                            (id_materia_prima, tipo_movimento, quantidade, observacao)
                        VALUES (%s, 'saida', %s, 'Baixa por produção de produto')
                        """,
                        (id_mp, float(qtd_receita) * float(quantidade)),
                    )
            conn.commit()
        log_info(f"Entrada produto ID {id_produto} | Qtd {quantidade}")
        return True
    except Exception as e:
        log_erro(f"Erro entrada_produto ID {id_produto}: {e}")
        return False
 
 
# =========================================================
# BALANÇO DIÁRIO (chamada em /estoque/fechamento)
# =========================================================
def obter_balanco_diario() -> list[dict]:
    """Retorna fabricado x vendido x sobra de hoje para cada produto."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        p.id_produto,
                        p.nome,
                        COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'entrada'
                                         THEN mov.quantidade ELSE 0 END), 0) AS fabricado,
                        COALESCE(SUM(iv.quantidade), 0) AS vendido
                    FROM produtos p
                    LEFT JOIN movimentacao_estoque mov
                        ON mov.id_produto = p.id_produto
                        AND DATE(mov.data_movimento) = CURRENT_DATE
                    LEFT JOIN itens_venda iv ON iv.id_produto = p.id_produto
                        AND iv.id_venda IN (
                            SELECT id_venda FROM vendas WHERE DATE(data_venda) = CURRENT_DATE
                        )
                    GROUP BY p.id_produto, p.nome
                    ORDER BY p.nome ASC
                    """
                )
                rows = cur.fetchall()
 
        return [
            {
                "id": r[0],
                "nome": r[1],
                "fabricado": float(r[2]),
                "vendido": float(r[3]),
                "sobrou": float(r[2]) - float(r[3]),
            }
            for r in rows
        ]
    except Exception as e:
        log_erro(f"Erro ao obter balanço diário: {e}")
        return []
