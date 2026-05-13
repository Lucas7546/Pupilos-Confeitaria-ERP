from modules.db import conectar
from datetime import datetime

# =========================
# ENTRADA ESTOQUE
# =========================
def entrada_estoque(materia_prima_id, quantidade):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO movimentacao_estoque (
            id_materia_prima,
            tipo_movimento,
            quantidade,
            observacao
        )
        VALUES (?, 'entrada', ?, 'Movimentação manual')
    """, (materia_prima_id, float(quantidade)))

    conexao.commit()
    conexao.close()


# =========================
# SAÍDA ESTOQUE
# =========================
def saida_estoque(materia_prima_id, quantidade, observacao='Movimentação manual'):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO movimentacao_estoque (
            id_materia_prima,
            tipo_movimento,
            quantidade,
            observacao
        )
        VALUES (?, 'saida', ?, ?)
    """, (materia_prima_id, float(quantidade), observacao))

    conexao.commit()
    conexao.close()


# =========================
# CALCULAR ESTOQUE ATUAL
# =========================
def calcular_estoque(materia_prima_id):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN tipo_movimento = 'entrada' THEN quantidade ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN tipo_movimento = 'saida' THEN quantidade ELSE 0 END), 0)
        FROM movimentacao_estoque
        WHERE id_materia_prima = ?
    """, (materia_prima_id,))

    resultado = cursor.fetchone()[0]
    conexao.close()

    return float(resultado or 0)


# =========================
# LISTAR MATÉRIA PRIMA
# =========================
def listar_materia_prima():
    con = conectar()
    cur = con.cursor()

    cur.execute("""
        SELECT 
            m.id_materia_prima,
            m.nome,
            m.unidade_medida,
            m.estoque_minimo,
            m.preco_unitario,
            (
                SELECT COALESCE(SUM(CASE WHEN tipo_movimento = 'entrada' THEN quantidade ELSE 0 END), 0) -
                       COALESCE(SUM(CASE WHEN tipo_movimento = 'saida' THEN quantidade ELSE 0 END), 0)
                FROM movimentacao_estoque mov
                WHERE mov.id_materia_prima = m.id_materia_prima
            ) as saldo_atual
        FROM materia_prima m
    """)

    materias_db = cur.fetchall()

    dados_formatados = []

    for m in materias_db:
        id_mp, nome, unidade, minimo, preco, atual = m

        status = "BAIXO" if (atual or 0) <= (minimo or 0) else "OK"

        dados_formatados.append((
            id_mp,
            nome,
            unidade,
            minimo,
            atual or 0,
            status
        ))

    con.close()
    return dados_formatados


# =========================
# CADASTRAR MATÉRIA PRIMA
# =========================
def cadastrar_materia_prima(nome, unidade, minimo, preco):
    try:
        con = conectar()
        cur = con.cursor()

        cur.execute("""
            INSERT INTO materia_prima (
                nome,
                unidade_medida,
                estoque_minimo,
                preco_unitario
            )
            VALUES (?, ?, ?, ?)
        """, (nome, unidade, float(minimo), float(preco)))

        con.commit()
        con.close()

        return True

    except Exception as e:
        print("Erro ao cadastrar:", e)
        return False


# =========================
# BUSCAR POR NOME
# =========================
def buscar_materia_prima_por_nome(nome):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id_materia_prima, nome, unidade_medida
        FROM materia_prima
        WHERE nome LIKE ?
    """, (f"%{nome}%",))

    resultados = cursor.fetchall()
    conexao.close()

    return resultados


# =========================
# COMPRA DE ESTOQUE (CORRIGIDO)
# =========================
def registrar_compra_estoque(id_materia_prima, quantidade_comprada, valor_total_pago):
    if quantidade_comprada <= 0:
        return False

    conexao = conectar()
    cursor = conexao.cursor()

    # calcula novo preço unitário
    novo_preco_unitario = valor_total_pago / quantidade_comprada

    # atualiza preço médio
    cursor.execute("""
        UPDATE materia_prima 
        SET preco_unitario = ? 
        WHERE id_materia_prima = ?
    """, (novo_preco_unitario, id_materia_prima))

    # registra entrada no estoque
    cursor.execute("""
        INSERT INTO movimentacao_estoque (
            id_materia_prima,
            tipo_movimento,
            quantidade,
            observacao
        )
        VALUES (?, 'entrada', ?, ?)
    """, (
        id_materia_prima,
        quantidade_comprada,
        f"Compra realizada em {datetime.now().strftime('%d/%m/%Y')}"
    ))

    conexao.commit()
    conexao.close()

    return True


def ajustar_estoque(id_mp, novo_valor):
    # UPDATE no banco ou lista
    pass