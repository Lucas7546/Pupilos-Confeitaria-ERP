from modules.db import conectar
from utils.logger import log_info, log_erro

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
        log_info(f"Produto '{nome}' cadastrado com sucesso.")
        return True
    except Exception as e:
        log_erro(f"Erro ao cadastrar produto '{nome}': {e}")
        return False
    finally:
        if con: con.close()

def buscar_produto_por_nome(nome):
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT id_produto, nome, preco_venda, categoria
            FROM produtos
            WHERE nome ILIKE %s AND ativo = 1
            ORDER BY nome ASC
        """, ('%' + nome + '%',))
        return cur.fetchall()
    except Exception as e:
        log_erro(f"Erro ao buscar produto por nome '{nome}': {e}")
        return []
    finally:
        if con: con.close()

def calcular_cenarios_preco(id_produto, preco_venda_atual):
    from modules.receitas import calcular_custo_receita
    
    try:
        custo_base = calcular_custo_receita(id_produto)
        if not custo_base or custo_base == 0:
            return {"atual": preco_venda_atual, "ponto_equilibrio": 0, "lucro_30": 0, "custo_real": 0}

        ponto_equilibrio = custo_base * 1.10 
        preco_com_margem = custo_base / 0.70

        return {
            "atual": preco_venda_atual,
            "ponto_equilibrio": round(ponto_equilibrio, 2),
            "lucro_30": round(preco_com_margem, 2),
            "custo_real": round(custo_base, 2)
        }
    except Exception as e:
        log_erro(f"Erro ao calcular cenários de preço para ID {id_produto}: {e}")
        return {}

def listar_todos():
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        cur.execute("SELECT id_produto, nome, preco_venda, categoria FROM produtos ORDER BY nome ASC")
        return cur.fetchall()
    except Exception as e:
        log_erro(f"Erro ao listar todos os produtos: {e}")
        return []
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
    except Exception as e:
        log_erro(f"Erro ao vincular insumo (Prod: {id_produto}, MP: {id_materia}): {e}")
        return False
    finally:
        if con: con.close()

def calcular_capacidade_geral():
    from modules.estoque import calcular_estoque
    produtos_lista = buscar_produto_por_nome("")
    capacidade_total = []
    con = None

    try:
        con = conectar()
        cur = con.cursor()

        for p in produtos_lista:
            id_p, nome_p = p[0], p[1]
            cur.execute("SELECT id_materia_prima, quantidade_utilizada FROM receitas WHERE id_produto = %s", (id_p,))
            ingredientes = cur.fetchall()

            if not ingredientes: continue

            limites = []
            for id_mp, qtd_necessaria in ingredientes:
                saldo_atual = calcular_estoque(id_mp)
                if qtd_necessaria > 0:
                    limites.append(saldo_atual // qtd_necessaria)

            capacidade_total.append({"nome": nome_p, "qtd": int(min(limites)) if limites else 0})
        
        return capacidade_total
    except Exception as e:
        log_erro(f"Erro ao calcular capacidade geral de produção: {e}")
        return []
    finally:
        if con: con.close()

def vincular_subproduto_ao_produto(id_produto, id_subproduto, quantidade):
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        cur.execute("SELECT id_receita FROM receitas WHERE id_produto = %s AND id_subproduto = %s", (id_produto, id_subproduto))
        existe = cur.fetchone()
        
        if existe:
            cur.execute("UPDATE receitas SET quantidade_utilizada = %s WHERE id_receita = %s", (quantidade, existe[0]))
        else:
            cur.execute("INSERT INTO receitas (id_produto, id_subproduto, id_materia_prima, quantidade_utilizada) VALUES (%s, %s, NULL, %s)", 
                        (id_produto, id_subproduto, quantidade))
        con.commit()
        return True
    except Exception as e:
        log_erro(f"Erro ao vincular subproduto {id_subproduto} ao produto {id_produto}: {e}")
        return False
    finally:
        if con: con.close()

def excluir_produto(id_produto):
    """Exclui produto e remove dependências (receitas e itens de venda)."""
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                # Remove receitas ligadas ao produto
                cursor.execute("DELETE FROM receitas WHERE id_produto = %s", (id_produto,))
                
                # Remove itens de venda ligados ao produto
                cursor.execute("DELETE FROM itens_venda WHERE id_produto = %s", (id_produto,))
                
                # Remove produto
                cursor.execute("DELETE FROM produtos WHERE id_produto = %s", (id_produto,))
                
                conn.commit()
                log_info(f"Produto {id_produto} excluído com sucesso.")
                return True
    except Exception as e:
        log_erro(f"Erro ao excluir produto {id_produto}: {e}")
        return False