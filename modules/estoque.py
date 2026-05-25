from modules.db import conectar
from datetime import datetime
from utils.logger import log_info, log_erro

# =========================================================
# ENTRADA ESTOQUE
# =========================================================
def entrada_estoque(materia_prima_id, quantidade):
    con = None
    cursor = None

    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            INSERT INTO movimentacao_estoque 
            (id_materia_prima, tipo_movimento, quantidade, observacao)
            VALUES (%s, 'entrada', %s, 'Movimentação manual')
        """, (materia_prima_id, float(quantidade)))

        con.commit()
        log_info(f"Entrada estoque MP {materia_prima_id} | Qtd: {quantidade}")
        return True

    except Exception as e:
        if con:
            con.rollback()
        log_erro(f"Erro entrada_estoque: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


# =========================================================
# SAÍDA ESTOQUE
# =========================================================
def saida_estoque(materia_prima_id, quantidade, observacao='Movimentação manual'):
    con = None
    cursor = None

    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            INSERT INTO movimentacao_estoque 
            (id_materia_prima, tipo_movimento, quantidade, observacao)
            VALUES (%s, 'saida', %s, %s)
        """, (materia_prima_id, float(quantidade), observacao))

        con.commit()
        log_info(f"Saída estoque MP {materia_prima_id} | Qtd: {quantidade}")
        return True

    except Exception as e:
        if con:
            con.rollback()
        log_erro(f"Erro saida_estoque: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


# =========================================================
# CALCULAR ESTOQUE
# =========================================================
def calcular_estoque(materia_prima_id):
    con = None
    cursor = None

    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN tipo_movimento IN ('entrada','ajuste') THEN quantidade ELSE 0 END),0)
                -
                COALESCE(SUM(CASE WHEN tipo_movimento = 'saida' THEN quantidade ELSE 0 END),0)
            FROM movimentacao_estoque
            WHERE id_materia_prima = %s
        """, (materia_prima_id,))

        return float(cursor.fetchone()[0] or 0)

    except Exception as e:
        log_erro(f"Erro calcular_estoque: {e}")
        return 0.0

    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()
# =========================================================
# LISTAR MATÉRIA PRIMA
# =========================================================
def listar_materia_prima():

    con = None

    try:

        con = conectar()

        cur = con.cursor()

        cur.execute("""

            SELECT 
                m.id_materia_prima,
                m.nome,
                m.unidade_medida,
                m.estoque_minimo,
                m.preco_unitario,

                COALESCE(
                    SUM(
                        CASE
                            WHEN mov.tipo_movimento IN ('entrada', 'ajuste')
                            THEN mov.quantidade
                            ELSE 0
                        END
                    ),
                    0
                )

                -

                COALESCE(
                    SUM(
                        CASE
                            WHEN mov.tipo_movimento = 'saida'
                            THEN mov.quantidade
                            ELSE 0
                        END
                    ),
                    0
                ) as saldo

            FROM materia_prima m

            LEFT JOIN movimentacao_estoque mov
                ON m.id_materia_prima = mov.id_materia_prima

            GROUP BY
                m.id_materia_prima,
                m.nome,
                m.unidade_medida,
                m.estoque_minimo,
                m.preco_unitario

            ORDER BY m.nome ASC

        """)

        materias = cur.fetchall()

        lista_final = []

        for m in materias:

            saldo = float(m[5])

            status = "BAIXO" if saldo <= float(m[3]) else "OK"

            lista_final.append(
                (
                    m[0],                 # id
                    m[1],                 # nome
                    m[2],                 # unidade
                    m[3],                 # estoque minimo
                    saldo,                # saldo atual
                    status,               # status
                    float(m[4])           # preco_unitario
                )
            )

        return lista_final
    except Exception as e:
        log_erro(f"Erro listar_materia_prima: {e}")
        return []

    finally:

        if con:
            con.close()

# =========================================================
# CADASTRAR MATÉRIA PRIMA
# =========================================================
def cadastrar_materia(nome, unidade, preco, estoque_inicial, estoque_minimo):
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO materia_prima (nome, unidade_medida, preco_unitario, estoque_minimo)
            VALUES (%s, %s, %s, %s) RETURNING id_materia_prima
        """, (nome, unidade, preco, estoque_minimo))
        id_mp = cur.fetchone()[0]
        
        if estoque_inicial > 0:
            cur.execute("""
                INSERT INTO movimentacao_estoque (id_materia_prima, tipo_movimento, quantidade, observacao)
                VALUES (%s, 'entrada', %s, 'Estoque inicial')
            """, (id_mp, estoque_inicial))
        
        con.commit()
        log_info(f"Matéria-prima cadastrada com sucesso: {nome} (ID: {id_mp})")
        return True
    except Exception as e:
        log_erro(f"Erro ao cadastrar matéria-prima '{nome}': {e}")
        return False
    finally:
        if con: con.close()

# =========================================================
# REGISTRAR COMPRA (ENTRADA + ATUALIZA PREÇO)
# =========================================================
def registrar_compra_estoque(id_materia_prima, quantidade_comprada, valor_total_pago):
    if quantidade_comprada <= 0:
        return False

    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        novo_preco_unitario = float(valor_total_pago) / float(quantidade_comprada)

        # atualiza preço médio
        cursor.execute("""
            UPDATE materia_prima 
            SET preco_unitario = %s 
            WHERE id_materia_prima = %s
        """, (novo_preco_unitario, id_materia_prima))

        # entrada no estoque
        data_str = datetime.now().strftime('%d/%m/%Y')
        cursor.execute("""
            INSERT INTO movimentacao_estoque 
            (id_materia_prima, tipo_movimento, quantidade, observacao)
            VALUES (%s, 'entrada', %s, %s)
        """, (
            id_materia_prima,
            float(quantidade_comprada),
            f"Compra em {data_str}"
        ))

        con.commit()
        log_info(f"Compra registrada. ID MP: {id_materia_prima}, Qtd: {quantidade_comprada}, Novo Preço: {novo_preco_unitario}")
        return True
    except Exception as e:
        log_erro(f"Erro ao registrar compra (ID MP: {id_materia_prima}): {e}")
        return False
    finally:
        if con: con.close()


# =========================================================
# AJUSTE DE ESTOQUE (MOVIMENTO AUDITÁVEL)
# =========================================================
def ajustar_estoque(id_mp, novo_valor):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            INSERT INTO movimentacao_estoque 
            (id_materia_prima, tipo_movimento, quantidade, observacao)
            VALUES (%s, 'ajuste', %s, 'Ajuste manual de estoque')
        """, (id_mp, float(novo_valor)))

        con.commit()
        log_info(f"Ajuste manual de estoque realizado. ID MP: {id_mp}, Quantidade ajustada: {novo_valor}")
    except Exception as e:
        log_erro(f"Erro ao ajustar estoque (ID MP: {id_mp}): {e}")
    finally:
        if con: con.close()


def previsao_demanda():

    conn = None

    try:

        conn = conectar()
        cursor = conn.cursor()

        # ===================================================
        # BUSCA TODAS AS MATÉRIAS-PRIMAS
        # ===================================================

        cursor.execute("""
            SELECT
                id_materia_prima,
                nome,
                unidade_medida,
                estoque_minimo
            FROM materia_prima
            ORDER BY nome ASC
        """)

        materias = cursor.fetchall()

        previsoes = []

        for mp in materias:

            id_mp = mp[0]
            nome = mp[1]
            unidade = mp[2]
            estoque_minimo = float(mp[3] or 0)

            # ===================================================
            # ESTOQUE ATUAL
            # ===================================================

            cursor.execute("""
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN tipo_movimento = 'entrada'
                            THEN quantidade
                            ELSE -quantidade
                        END
                    ), 0)
                FROM movimentacao_estoque
                WHERE id_materia_prima = %s
            """, (id_mp,))

            estoque_atual = float(cursor.fetchone()[0] or 0)

            # ===================================================
            # CONSUMO ÚLTIMOS 7 DIAS
            # ===================================================

            data_inicio = datetime.now() - timedelta(days=7)

            cursor.execute("""
                SELECT
                    COALESCE(SUM(quantidade), 0)
                FROM movimentacao_estoque
                WHERE id_materia_prima = %s
                AND tipo_movimento = 'saida'
                AND data_movimento >= %s
            """, (
                id_mp,
                data_inicio
            ))

            consumo_7d = float(cursor.fetchone()[0] or 0)

            # ===================================================
            # MÉDIA DIÁRIA
            # ===================================================

            media_diaria = consumo_7d / 7 if consumo_7d > 0 else 0

            # ===================================================
            # PREVISÃO 15 DIAS
            # ===================================================

            consumo_15d = round(media_diaria * 15, 2)

            # ===================================================
            # PREVISÃO 7 DIAS
            # ===================================================

            consumo_previsto = round(media_diaria * 7, 2)

            # ===================================================
            # DIAS RESTANTES
            # ===================================================

            if media_diaria > 0:
                dias_restantes = round(estoque_atual / media_diaria, 1)
            else:
                dias_restantes = 999

            # ===================================================
            # RISCO
            # ===================================================

            if dias_restantes < 2:
                risco = "CRÍTICO"

            elif dias_restantes < 5:
                risco = "ALTO"

            elif dias_restantes < 10:
                risco = "MODERADO"

            else:
                risco = "BAIXO"

            # ===================================================
            # SUGESTÃO DE COMPRA
            # ===================================================

            sugestao_compra = max(
                round(consumo_15d - estoque_atual, 2),
                estoque_minimo
            )

            previsoes.append({

                "materia_prima": nome,
                "unidade": unidade,

                "estoque_atual": round(estoque_atual, 2),

                "media_diaria": round(media_diaria, 2),

                "consumo_previsto": consumo_previsto,

                "consumo_15d": consumo_15d,

                "dias_restantes": dias_restantes,

                "risco": risco,

                "sugestao_compra": round(sugestao_compra, 2)

            })

        return previsoes

    except Exception as e:
        log_erro(f"Erro na geração da previsão de demanda: {e}")
        return []

    finally:

        if conn:
            conn.close()


# =========================================================
# EXTRATO DE MOVIMENTAÇÕES UNIFICADO (HISTÓRICO CRONOLÓGICO)
# =========================================================
def obter_historico_movimentacoes():
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        
        # A query faz um COALESCE para identificar o nome do item independente do tipo
        # E identifica a categoria real do item movimentado
        cur.execute("""
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
        """)
        
        registros = cur.fetchall()
        historico = []
        
        for reg in registros:
            historico.append({
                "id": reg[0],
                "data": reg[1].strftime("%d/%m/%Y %H:%M") if reg[1] else "-",
                "item": reg[2],
                "tipo_item": reg[3],
                "tipo_movimento": reg[4].upper(), # ENTRADA, SAIDA, AJUSTE
                "quantidade": float(reg[5]),
                "unidade": reg[6],
                "observacao": reg[7]
            })
            
        return historico
    except Exception as e:
        log_erro(f"Erro ao obter histórico de movimentações: {e}")
        return []
    finally:
        if con:
            con.close()
    

# =========================
# EXCLUIR MATÉRIA PRIMA
# =========================
def excluir_materia_prima(id_mp):
    """Exclui matéria-prima e remove suas dependências (receitas e movimentações)."""
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                # Remove receitas vinculadas
                cursor.execute("DELETE FROM receitas WHERE id_materia_prima = %s", (id_mp,))
                
                # Remove movimentações
                cursor.execute("DELETE FROM movimentacao_estoque WHERE id_materia_prima = %s", (id_mp,))
                
                # Remove matéria-prima
                cursor.execute("DELETE FROM materia_prima WHERE id_materia_prima = %s", (id_mp,))
                
                conn.commit()
                log_info(f"Matéria-prima ID {id_mp} excluída com sucesso.")
                return True
    except Exception as e:
        log_erro(f"Erro ao excluir matéria-prima ID {id_mp}: {e}")
        return False
    
# =========================
# ATUALIZAR MATÉRIA PRIMA
# =========================
def atualizar_materia_prima(id_mp, nome, preco, unidade, quantidade):
    """Atualiza dados da matéria-prima e registra ajuste manual no estoque se necessário."""
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE materia_prima
                    SET nome = %s, preco_unitario = %s, unidade_medida = %s
                    WHERE id_materia_prima = %s
                """, (nome, preco, unidade, id_mp))

                # Ajuste de estoque se houver quantidade informada
                if quantidade and float(quantidade) > 0:
                    cursor.execute("""
                        INSERT INTO movimentacao_estoque (id_materia_prima, tipo_movimento, quantidade, observacao)
                        VALUES (%s, 'entrada', %s, 'Ajuste manual de estoque')
                    """, (id_mp, quantidade))

                conn.commit()
                log_info(f"Matéria-prima ID {id_mp} atualizada com sucesso.")
                return True
    except Exception as e:
        log_erro(f"Erro ao atualizar matéria-prima ID {id_mp}: {e}")
        return False