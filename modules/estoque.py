from modules.db import conectar
from datetime import datetime

# =========================================================
# ENTRADA ESTOQUE
# =========================================================
def entrada_estoque(materia_prima_id, quantidade):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            INSERT INTO movimentacao_estoque 
            (id_materia_prima, tipo_movimento, quantidade, observacao)
            VALUES (%s, 'entrada', %s, 'Movimentação manual')
        """, (materia_prima_id, float(quantidade)))

        con.commit()

    except Exception as e:
        print(f"Erro entrada_estoque: {e}")

    finally:
        if con:
            con.close()


# =========================================================
# SAÍDA ESTOQUE
# =========================================================
def saida_estoque(materia_prima_id, quantidade, observacao='Movimentação manual'):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            INSERT INTO movimentacao_estoque 
            (id_materia_prima, tipo_movimento, quantidade, observacao)
            VALUES (%s, 'saida', %s, %s)
        """, (materia_prima_id, float(quantidade), observacao))

        con.commit()

    except Exception as e:
        print(f"Erro saida_estoque: {e}")

    finally:
        if con:
            con.close()


# =========================================================
# CALCULAR ESTOQUE ATUAL
# =========================================================
def calcular_estoque(materia_prima_id):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN tipo_movimento IN ('entrada', 'ajuste') THEN quantidade ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN tipo_movimento = 'saida' THEN quantidade ELSE 0 END), 0)
            FROM movimentacao_estoque
            WHERE id_materia_prima = %s
        """, (materia_prima_id,))

        resultado = cursor.fetchone()[0]
        return float(resultado or 0)

    except Exception as e:
        print(f"Erro calcular_estoque: {e}")
        return 0.0

    finally:
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
                m.id_materia_prima, m.nome, m.unidade_medida, m.estoque_minimo, m.preco_unitario,
                COALESCE(SUM(CASE WHEN mov.tipo_movimento IN ('entrada', 'ajuste') THEN mov.quantidade ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'saida' THEN mov.quantidade ELSE 0 END), 0) as saldo
            FROM materia_prima m
            LEFT JOIN movimentacao_estoque mov ON m.id_materia_prima = mov.id_materia_prima
            GROUP BY m.id_materia_prima, m.nome, m.unidade_medida, m.estoque_minimo, m.preco_unitario
            ORDER BY m.nome ASC
        """)
        materias = cur.fetchall()
        return [(m[0], m[1], m[2], m[3], float(m[5]), "BAIXO" if float(m[5]) <= float(m[3]) else "OK") for m in materias]
    finally:
        if con: con.close()

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
        return True
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
        cursor.execute("""
            INSERT INTO movimentacao_estoque 
            (id_materia_prima, tipo_movimento, quantidade, observacao)
            VALUES (%s, 'entrada', %s, %s)
        """, (
            id_materia_prima,
            float(quantidade_comprada),
            f"Compra em {datetime.now().strftime('%d/%m/%Y')}"
        ))

        con.commit()
        return True

    except Exception as e:
        print(f"Erro registrar_compra_estoque: {e}")
        return False

    finally:
        if con:
            con.close()


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

    except Exception as e:
        print(f"Erro ajustar_estoque: {e}")

    finally:
        if con:
            con.close()