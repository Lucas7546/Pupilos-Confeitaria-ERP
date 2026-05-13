from modules.db import conectar
from modules.estoque import buscar_materia_prima_por_nome

# =========================
# CADASTRAR/VINCULAR INGREDIENTE
# =========================
def cadastrar_receita(id_produto, id_materia_prima, quantidade):
    conexao = conectar()
    cursor = conexao.cursor()
    
    # Verifica se esse ingrediente já está na receita para não duplicar, 
    # apenas atualizar a quantidade se necessário
    cursor.execute("""
        SELECT id_receita FROM receitas 
        WHERE id_produto = ? AND id_materia_prima = ?
    """, (id_produto, id_materia_prima))
    
    existe = cursor.fetchone()
    
    if existe:
        cursor.execute("""
            UPDATE receitas SET quantidade_utilizada = ?
            WHERE id_produto = ? AND id_materia_prima = ?
        """, (quantidade, id_produto, id_materia_prima))
    else:
        cursor.execute("""
            INSERT INTO receitas (id_produto, id_materia_prima, quantidade_utilizada)
            VALUES (?, ?, ?)
        """, (id_produto, id_materia_prima, quantidade))

    conexao.commit()
    conexao.close()
    return True

# =========================
# LISTAR DETALHES DA RECEITA (Para o Frontend)
# =========================
def listar_itens_receita(id_produto):
    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("""
        SELECT mp.nome, r.quantidade_utilizada, mp.unidade_medida, mp.preco_unitario
        FROM receitas r
        JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
        WHERE r.id_produto = ?
    """, (id_produto,))
    itens = cursor.fetchall()
    conexao.close()
    return itens

# =========================
# VALIDAR ESTOQUE
# =========================
def validar_estoque_suficiente(id_produto, quantidade_venda):
    from modules.estoque import calcular_estoque
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id_materia_prima, quantidade_utilizada
        FROM receitas
        WHERE id_produto = ?
    """, (id_produto,))

    ingredientes = cursor.fetchall()
    
    # Se não tem receita cadastrada, avisamos que não dá pra validar
    if not ingredientes:
        return True # Ou False, dependendo se você quer obrigar a ter receita

    for id_mp, qtd_necessaria in ingredientes:
        estoque_atual = calcular_estoque(id_mp)
        # Verifica se o que tem no estoque supre (qtd da receita * unidades vendidas)
        if estoque_atual < (qtd_necessaria * quantidade_venda):
            conexao.close()
            return False

    conexao.close()
    return True

# =========================
# CALCULAR CUSTO TOTAL DA RECEITA
# =========================
def calcular_custo_receita(id_produto):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT r.quantidade_utilizada, mp.preco_unitario
        FROM receitas r
        JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
        WHERE r.id_produto = ?
    """, (id_produto,))

    linhas = cursor.fetchall()
    total = sum(qtd * preco for qtd, preco in linhas)

    conexao.close()
    return total