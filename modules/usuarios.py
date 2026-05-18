from modules.db import conectar
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import DictCursor


# =========================
# BUSCAR USUÁRIO
# =========================
def buscar_usuario(username):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor(cursor_factory=DictCursor)

        cursor.execute("""
            SELECT id_usuario, username, senha, nivel, ativo
            FROM usuarios
            WHERE username = %s
        """, (username.strip(),))

        return cursor.fetchone()

    except Exception as e:
        print(f"Erro ao buscar usuário: {e}")
        return None

    finally:
        if conn:
            conn.close()


# =========================
# CRIAR USUÁRIO (FORÇADO PADRÃO LIMPO)
# =========================
def criar_usuario(username, senha, nivel="colaborador"):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        username = username.strip()
        nivel = nivel.strip().lower()

        # valida nível
        if nivel not in ["admin", "socios", "colaborador"]:
            raise Exception("Nível inválido")

        # checar duplicado
        cursor.execute("""
            SELECT id_usuario FROM usuarios WHERE username = %s
        """, (username,))

        if cursor.fetchone():
            raise Exception("Usuário já existe")

        senha_hash = generate_password_hash(senha)

        cursor.execute("""
            INSERT INTO usuarios (username, senha, nivel, ativo)
            VALUES (%s, %s, %s, 1)
        """, (username, senha_hash, nivel))

        conn.commit()
        return True

    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        return False

    finally:
        if conn:
            conn.close()

# =========================================================
# GESTÃO DE LOGS (Auditoria no Postgres)
# =========================================================
def registrar_log_db(usuario, acao, modulo, detalhe):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (usuario, acao, modulo, detalhe)
            VALUES (%s, %s, %s, %s)
        """, (usuario, acao, modulo, detalhe))
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"Erro ao registrar log no banco: {e}")
    finally:
        if conn:
            conn.close()

def listar_logs_auditoria(limite=100):
    conn = None
    try:
        conn = conectar()
        # Usamos DictCursor para que o HTML possa acessar por log['usuario']
        from psycopg2.extras import DictCursor
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        cursor.execute("""
            SELECT usuario, acao, modulo, detalhe, data 
            FROM logs 
            ORDER BY data DESC 
            LIMIT %s
        """, (limite,))
        
        logs = cursor.fetchall()
        cursor.close()
        return logs
    except Exception as e:
        print(f"Erro ao listar auditoria: {e}")
        return []
    finally:
        if conn:
            conn.close()

# =========================
# LISTAR USUÁRIOS
# =========================
def listar_usuarios():
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id_usuario, username, nivel, ativo, data_cadastro
            FROM usuarios
            ORDER BY id_usuario DESC
        """)

        return cursor.fetchall()

    finally:
        if conn:
            conn.close()

# =========================
# VALIDAR LOGIN (IMPORTANTE)
# =========================
def validar_login(username, senha):
    user = buscar_usuario(username)

    if not user:
        return None

    if not user["ativo"]:
        return None

    if check_password_hash(user["senha"], senha):
        return {
            "id": user["id_usuario"],
            "username": user["username"],
            "nivel": user["nivel"]
        }

    return None

# =========================
# ALTERAR STATUS
# =========================
def alterar_status(id_usuario, ativo):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE usuarios
            SET ativo = %s
            WHERE id_usuario = %s
        """, (ativo, id_usuario))

        conn.commit()
        return True

    finally:
        if conn:
            conn.close()
            

def buscar_usuario_id(id_usuario):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_usuario, username, senha, nivel, ativo, data_cadastro
            FROM usuarios
            WHERE id_usuario = %s
        """, (id_usuario,))
        usuario = cursor.fetchone()
        cursor.close()
        return usuario
    except Exception as e:
        print(f"Erro ao buscar usuário por ID: {e}")
        return None
    finally:
        if conn:
            conn.close()

def atualizar_nivel(id_usuario, novo_nivel):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE usuarios 
            SET nivel = %s 
            WHERE id_usuario = %s
        """, (novo_nivel.lower(), id_usuario))
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"Erro ao atualizar nível: {e}")
    finally:
        if conn:
            conn.close()


# =========================
# EXCLUIR USUÁRIO
# =========================
def excluir_usuario(id_usuario):
    conn = None

    try:
        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM usuarios
            WHERE id_usuario = %s
        """, (id_usuario,))

        conn.commit()

        return True

    except Exception as e:

        print(f"Erro ao excluir usuário: {e}")

        return False

    finally:

        if conn:
            conn.close()




# =========================
# EXCLUIR PRODUTO
# =========================
def excluir_produto(id_produto):

    conn = None

    try:

        conn = conectar()
        cursor = conn.cursor()

        # Remove receitas ligadas ao produto
        cursor.execute("""
            DELETE FROM receitas
            WHERE id_produto = %s
        """, (id_produto,))

        # Remove itens de venda ligados ao produto
        cursor.execute("""
            DELETE FROM itens_venda
            WHERE id_produto = %s
        """, (id_produto,))

        # Remove produto
        cursor.execute("""
            DELETE FROM produtos
            WHERE id_produto = %s
        """, (id_produto,))

        conn.commit()

        return True

    except Exception as e:

        if conn:
            conn.rollback()

        print(f"ERRO EXCLUIR PRODUTO: {e}")

        return False

    finally:

        if conn:
            conn.close()


# =========================
# EXCLUIR MATÉRIA PRIMA
# =========================
def excluir_materia_prima(id_mp):

    conn = None

    try:

        conn = conectar()
        cursor = conn.cursor()

        # Remove receitas vinculadas
        cursor.execute("""
            DELETE FROM receitas
            WHERE id_materia_prima = %s
        """, (id_mp,))

        # Remove movimentações
        cursor.execute("""
            DELETE FROM movimentacao_estoque
            WHERE id_materia_prima = %s
        """, (id_mp,))

        # Remove matéria-prima
        cursor.execute("""
            DELETE FROM materia_prima
            WHERE id_materia_prima = %s
        """, (id_mp,))

        conn.commit()

        return True

    except Exception as e:

        if conn:
            conn.rollback()

        print(f"Erro excluir matéria-prima: {e}")

        return False

    finally:

        if conn:
            conn.close()


# =========================
# EXCLUIR VENDA + ROLLBACK
# =========================
def excluir_venda(id_venda):

    conn = None

    try:

        conn = conectar()

        cursor = conn.cursor()

        # =========================================
        # VERIFICA SE VENDA EXISTE
        # =========================================

        cursor.execute("""
            SELECT id_venda
            FROM vendas
            WHERE id_venda = %s
        """, (id_venda,))

        venda = cursor.fetchone()

        if not venda:

            print(f"Venda {id_venda} não encontrada")

            return False

        # =========================================
        # BUSCA ITENS DA VENDA
        # =========================================

        cursor.execute("""
            SELECT
                iv.id_produto,
                iv.quantidade
            FROM itens_venda iv
            WHERE iv.id_venda = %s
        """, (id_venda,))

        itens = cursor.fetchall()

        if not itens:

            print(f"Venda {id_venda} sem itens")

        # =========================================
        # DEVOLVE ESTOQUE
        # =========================================

        for id_produto, quantidade_vendida in itens:

            cursor.execute("""
                SELECT
                    id_materia_prima,
                    quantidade_utilizada
                FROM receitas
                WHERE id_produto = %s
            """, (id_produto,))

            ingredientes = cursor.fetchall()

            for id_mp, qtd_receita in ingredientes:

                qtd_retorno = (
                    float(qtd_receita) *
                    float(quantidade_vendida)
                )

                # =========================================
                # REGISTRA RETORNO NO ESTOQUE
                # =========================================

                cursor.execute("""
                    INSERT INTO movimentacao_estoque (
                        id_materia_prima,
                        tipo_movimento,
                        quantidade,
                        observacao
                    )
                    VALUES (
                        %s,
                        'entrada',
                        %s,
                        %s
                    )
                """, (
                    id_mp,
                    qtd_retorno,
                    f'ROLLBACK AUTOMÁTICO VENDA ID {id_venda}'
                ))

        # =========================================
        # REMOVE ITENS DA VENDA
        # =========================================

        cursor.execute("""
            DELETE FROM itens_venda
            WHERE id_venda = %s
        """, (id_venda,))

        # =========================================
        # REMOVE VENDA
        # =========================================

        cursor.execute("""
            DELETE FROM vendas
            WHERE id_venda = %s
        """, (id_venda,))

        conn.commit()

        print(f"Venda {id_venda} excluída com rollback realizado")

        return True

    except Exception as e:

        if conn:
            conn.rollback()

        print(f"Erro excluir venda: {e}")

        return False

    finally:

        if conn:
            conn.close()

# =========================
# ATUALIZAR PRODUTO
# =========================
def update_produto(id_produto, nome, preco):

    conn = None

    try:

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE produtos
            SET
                nome = %s,
                preco_venda = %s
            WHERE id_produto = %s
        """, (
            nome,
            preco,
            id_produto
        ))

        conn.commit()

        return True

    except Exception as e:

        print(f"Erro update produto: {e}")

        return False

    finally:

        if conn:
            conn.close()


# =========================
# ATUALIZAR MATÉRIA PRIMA
# =========================
def atualizar_materia_prima(
    id_mp,
    nome,
    preco,
    unidade,
    quantidade
):

    conn = None

    try:

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE materia_prima
            SET
                nome = %s,
                preco_unitario = %s,
                unidade_medida = %s
            WHERE id_materia_prima = %s
        """, (
            nome,
            preco,
            unidade,
            id_mp
        ))

        # =====================================================
        # AJUSTE DE ESTOQUE
        # =====================================================

        if quantidade and float(quantidade) > 0:

            cursor.execute("""
                INSERT INTO movimentacao_estoque (
                    id_materia_prima,
                    tipo_movimento,
                    quantidade,
                    observacao
                )
                VALUES (%s, 'entrada', %s, %s)
            """, (
                id_mp,
                quantidade,
                'Ajuste manual de estoque'
            ))

        conn.commit()

        return True

    except Exception as e:

        print(f"Erro atualizar MP: {e}")

        return False

    finally:

        if conn:
            conn.close()