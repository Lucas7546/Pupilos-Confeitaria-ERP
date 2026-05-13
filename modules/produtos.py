from modules.db import conectar

def cadastrar_produto(nome, preco_venda):
    """
    Cadastra um novo produto no banco Postgres.
    """
    con = None
    try:
        con = conectar()
        cur = con.cursor()

        cur.execute("""
            INSERT INTO produtos (nome, preco_venda)
            VALUES (%s, %s)
        """, (nome, preco_venda))

        con.commit()
        cur.close()
        return True

    except Exception as e:
        print(f"Erro ao cadastrar produto: {e}")
        return False
    finally:
        if con:
            con.close()

def buscar_produto_por_nome(nome):
    """
    Busca produtos usando busca textual insensível a maiúsculas (ILIKE).
    """
    con = None
    try:
        con = conectar()
        cur = con.cursor()

        # O Postgres usa %s para parâmetros e ILIKE para busca parcial sem case-sensitive
        cur.execute("""
            SELECT id_produto, nome, preco_venda
            FROM produtos
            WHERE nome ILIKE %s
            ORDER BY nome ASC
        """, ('%' + nome + '%',))

        produtos = cur.fetchall()
        cur.close()
        return produtos
    except Exception as e:
        print(f"Erro ao buscar produtos: {e}")
        return []
    finally:
        if con:
            con.close()

def calcular_cenarios_preco(id_produto, preco_venda_atual):
    """
    Compara o preço atual com o custo real para sugerir o melhor valor.
    """
    from modules.receitas import calcular_custo_receita
    
    custo_base = calcular_custo_receita(id_produto)
    
    if not custo_base or custo_base == 0:
        return {
            "atual": preco_venda_atual,
            "ponto_equilibrio": 0,
            "lucro_30": 0,
            "custo_real": 0
        }

    # Ponto de Equilíbrio (Custo + 10% para Gás/Limpeza/Variáveis)
    ponto_equilibrio = custo_base * 1.10 

    # Margem de 30% sobre o preço de venda (Fórmula de markup líquido)
    preco_com_margem = custo_base / 0.70

    return {
        "atual": preco_venda_atual,
        "ponto_equilibrio": round(ponto_equilibrio, 2),
        "lucro_30": round(preco_com_margem, 2),
        "custo_real": round(custo_base, 2)
    }

def calcular_capacidade_geral():
    """
    Calcula quantos produtos podem ser feitos com o estoque atual de matéria-prima.
    """
    from modules.estoque import calcular_estoque

    produtos_lista = buscar_produto_por_nome("")
    capacidade_total = []
    con = None

    try:
        con = conectar()
        cur = con.cursor()

        for p in produtos_lista:
            id_p, nome_p, preco = p

            cur.execute("""
                SELECT id_materia_prima, quantidade_utilizada
                FROM receitas
                WHERE id_produto = %s
            """, (id_p,))

            ingredientes = cur.fetchall()

            if not ingredientes:
                continue

            limites = []

            for id_mp, qtd_necessaria in ingredientes:
                saldo_atual = calcular_estoque(id_mp)

                if qtd_necessaria > 0:
                    # Divisão inteira no Python (//) para saber unidades completas
                    pode_fazer = saldo_atual // qtd_necessaria
                    limites.append(pode_fazer)

            capacidade_real = int(min(limites)) if limites else 0

            capacidade_total.append({
                "nome": nome_p,
                "qtd": capacidade_real
            })
        
        cur.close()
    except Exception as e:
        print(f"Erro ao calcular capacidade: {e}")
    finally:
        if con:
            con.close()

    return capacidade_total