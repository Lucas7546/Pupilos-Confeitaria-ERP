from modules.db import conectar

def cadastrar_produto(nome, preco_venda, categoria="Geral"):
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO produtos (nome, preco_venda, categoria)
            VALUES (%s, %s, %s)
        """, (nome, preco_venda, categoria))
        con.commit()
        return True
    except Exception as e:
        print(f"Erro ao cadastrar produto: {e}")
        return False
    finally:
        if con: con.close()

def buscar_produto_por_nome(nome):
    con = None
    try:
        con = conectar()
        cur = con.cursor()

        cur.execute("""
            SELECT 
                id_produto,
                nome,
                preco_venda,
                categoria
            FROM produtos
            WHERE nome ILIKE %s
            AND ativo = 1
            ORDER BY nome ASC
        """, ('%' + nome + '%',))

        return cur.fetchall()

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



def listar_todos():
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        # id_produto, nome, preco_venda conforme seu SQL
        cur.execute("SELECT id_produto, nome, preco_venda, categoria FROM produtos ORDER BY nome ASC")
        return cur.fetchall()
    finally:
        if con: con.close()


def vincular_insumo(id_produto, id_materia, quantidade):
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        cur.execute("SELECT id_receita FROM receitas WHERE id_produto = %s AND id_materia_prima = %s", (id_produto, id_materia))
        existe = cur.fetchone()
        
        if existe:
            cur.execute("UPDATE receitas SET quantidade_utilizada = %s WHERE id_receita = %s", (quantidade, existe[0]))
        else:
            cur.execute("INSERT INTO receitas (id_produto, id_materia_prima, quantidade_utilizada) VALUES (%s, %s, %s)", 
                        (id_produto, id_materia, quantidade))
        con.commit()
        return True
    finally:
        if con: con.close()


def excluir_produto(id_produto):
    with obter_conexao() as conn:
        with conn.cursor() as cursor:
            # Importante: Se o produto estiver em uma venda, 
            # pode dar erro de FK. Se quiser deletar mesmo assim:
            cursor.execute("DELETE FROM produtos WHERE id = %s", (id_produto,))
            conn.commit()

def excluir_venda(id_venda):
    with obter_conexao() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM vendas WHERE id = %s", (id_venda,))
            conn.commit()

def calcular_capacidade_geral():

    from modules.estoque import calcular_estoque

    produtos_lista = buscar_produto_por_nome("")
    capacidade_total = []

    con = None

    try:
        con = conectar()
        cur = con.cursor()

        for p in produtos_lista:

            id_p = p[0]
            nome_p = p[1]

            cur.execute("""
                SELECT
                    id_materia_prima,
                    quantidade_utilizada
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
                    pode_fazer = saldo_atual // qtd_necessaria
                    limites.append(pode_fazer)

            capacidade_real = int(min(limites)) if limites else 0

            capacidade_total.append({
                "nome": nome_p,
                "qtd": capacidade_real
            })

        cur.close()

    except Exception as e:
        print(f"Erro calcular capacidade: {e}")

    finally:
        if con:
            con.close()

    return capacidade_total