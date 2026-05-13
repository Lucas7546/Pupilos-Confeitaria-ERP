import sqlite3
from modules.db import conectar

def cadastrar_produto(nome, preco_venda):
    try:
        con = conectar()
        cur = con.cursor()
        cur.execute("INSERT INTO produtos (nome, preco_venda) VALUES (?, ?)", (nome, preco_venda))
        con.commit()
        con.close()
        return True
    except:
        return False

def buscar_produto_por_nome(nome):
    conexao = conectar()
    cur = conexao.cursor()
    
    # O ERRO ESTAVA AQUI: Mudamos 'id' para 'id_produto'
    cur.execute("SELECT id_produto, nome, preco_venda FROM produtos WHERE nome LIKE ?", ('%' + nome + '%',))
    
    produtos = cur.fetchall()
    conexao.close()
    return produtos

def calcular_cenarios_preco(id_produto, preco_venda_atual):
    """
    Compara o preço atual com o custo real para sugerir o melhor valor.
    """
    from modules.receitas import calcular_custo_receita
    
    custo_base = calcular_custo_receita(id_produto)
    
    if custo_base == 0:
        return {
            "atual": preco_venda_atual,
            "ponto_equilibrio": 0,
            "lucro_30": 0,
            "custo_real": 0
        }

    # Ponto de Equilíbrio (Custo + 10% para Gás/Limpeza)
    ponto_equilibrio = custo_base * 1.10 

    # Margem de 30% Líquida (Para sobrar 30% livre após pagar o custo)
    preco_com_margem = custo_base / 0.70

    return {
        "atual": preco_venda_atual,
        "ponto_equilibrio": round(ponto_equilibrio, 2),
        "lucro_30": round(preco_com_margem, 2),
        "custo_real": round(custo_base, 2)
    }

def calcular_capacidade_geral():
    """
    Analisa o estoque atual e diz quanto de CADA produto ela consegue fazer.
    Lógica: O ingrediente que tiver menos saldo limita a produção total.
    """
    from modules.estoque import calcular_estoque
    
    produtos_lista = buscar_produto_por_nome("") # Puxa todos os produtos
    capacidade_total = []

    for p in produtos_lista:
        id_p, nome_p, preco = p
        
        con = conectar()
        cur = con.cursor()
        # Busca o que esse produto gasta de cada ingrediente
        cur.execute("SELECT id_materia_prima, quantidade_utilizada FROM receitas WHERE id_produto = ?", (id_p,))
        ingredientes = cur.fetchall()
        con.close()

        if not ingredientes:
            continue

        limites = []
        for id_mp, qtd_necessaria in ingredientes:
            saldo_atual = calcular_estoque(id_mp)
            if qtd_necessaria > 0:
                # Ex: Se tenho 10 latas e cada receita usa 1, posso fazer 10.
                pode_fazer = saldo_atual // qtd_necessaria
                limites.append(pode_fazer)
        
        # O menor valor da lista é o limite real (Gargalo)
        capacidade_real = int(min(limites)) if limites else 0
        capacidade_total.append({"nome": nome_p, "qtd": capacidade_real})

    return capacidade_total