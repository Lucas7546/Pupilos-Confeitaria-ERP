import sqlite3
from datetime import datetime, timedelta
from modules.db import conectar
from modules.receitas import validar_estoque_suficiente, calcular_custo_receita

# ===================================================
# GESTÃO DE ESTOQUE VINCULADO À VENDA
# ===================================================
def baixar_estoque_por_receita(id_produto, quantidade_vendida):
    conexao = conectar()
    cursor = conexao.cursor()
    
    cursor.execute("""
        SELECT id_materia_prima, quantidade_utilizada 
        FROM receitas 
        WHERE id_produto = ?
    """, (id_produto,))
    
    ingredientes = cursor.fetchall()
    
    for id_mp, qtd_na_receita in ingredientes:
        qtd_total_saida = qtd_na_receita * quantidade_vendida
        
        cursor.execute("""
            INSERT INTO movimentacao_estoque (
                id_materia_prima, tipo_movimento, quantidade, observacao
            )
            VALUES (?, 'saida', ?, ?)
        """, (id_mp, qtd_total_saida, f"Baixa automática: Venda de {quantidade_vendida} unid."))
        
    conexao.commit()
    conexao.close()

# =========================
# OPERAÇÃO DE VENDA
# =========================
def vender_produto(id_produto, quantidade, preco, canal="manual"):
    if not validar_estoque_suficiente(id_produto, quantidade):
        return False, "Estoque insuficiente para produzir esta quantidade."

    conexao = conectar()
    cursor = conexao.cursor()

    custo_unitario = calcular_custo_receita(id_produto)
    receita_total = float(preco) * int(quantidade)
    lucro_total = receita_total - (custo_unitario * int(quantidade))
    data_venda = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        INSERT INTO vendas (valor_total, canal_venda, lucro, data_venda)
        VALUES (?, ?, ?, ?)
    """, (receita_total, canal, lucro_total, data_venda))

    id_venda = cursor.lastrowid

    cursor.execute("""
        INSERT INTO itens_venda (id_venda, id_produto, quantidade, valor_unitario)
        VALUES (?, ?, ?, ?)
    """, (id_venda, id_produto, quantidade, preco))

    conexao.commit()
    conexao.close()

    baixar_estoque_por_receita(id_produto, quantidade)
    return True, "Venda realizada com sucesso!"

# ===================================================
# GESTÃO DE DESPESAS (CUSTOS FIXOS)
# ===================================================
def registrar_despesa(descricao, valor, categoria):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO despesas (descricao, valor, categoria) 
        VALUES (?, ?, ?)
    """, (descricao, valor, categoria))
    conn.commit()
    conn.close()

def listar_despesas(dias=30):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_despesa, descricao, valor, categoria 
        FROM despesas 
        WHERE data_despesa >= datetime('now', ?)
    """, (f'-{dias} days',))
    dados = cursor.fetchall()
    conn.close()
    return dados

# ===================================================
# RELATÓRIOS E INTELIGÊNCIA FINANCEIRA
# ===================================================
def obter_custo_total_vendas(dias=30):
    conn = conectar()
    cursor = conn.cursor()
    query = """
    SELECT SUM(iv.quantidade * r.quantidade_utilizada * mp.preco_unitario)
    FROM itens_venda iv
    JOIN vendas v ON iv.id_venda = v.id_venda
    JOIN receitas r ON iv.id_produto = r.id_produto
    JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
    WHERE v.data_venda >= datetime('now', ?)
    """
    cursor.execute(query, (f'-{dias} days',))
    resultado = cursor.fetchone()[0]
    conn.close()
    return resultado if resultado else 0

def obter_resumo_periodo(dias=7):
    conexao = conectar()
    cursor = conexao.cursor()
    data_inicio = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("""
        SELECT SUM(valor_total), SUM(lucro), COUNT(id_venda) 
        FROM vendas 
        WHERE data_venda >= ?
    """, (data_inicio,))
    res = cursor.fetchone()
    
    cursor.execute("""
        SELECT p.nome, SUM(iv.quantidade), SUM(iv.quantidade * iv.valor_unitario)
        FROM itens_venda iv
        JOIN produtos p ON iv.id_produto = p.id_produto
        JOIN vendas v ON iv.id_venda = v.id_venda
        WHERE v.data_venda >= ?
        GROUP BY p.nome
        ORDER BY SUM(iv.quantidade) DESC
    """, (data_inicio,))
    ranking = cursor.fetchall()
    
    conexao.close()
    return {
        "faturamento": res[0] or 0.0,
        "lucro": res[1] or 0.0,
        "total_vendas": res[2] or 0,
        "ranking": ranking
    }