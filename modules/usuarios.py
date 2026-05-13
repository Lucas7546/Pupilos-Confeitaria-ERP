from modules.db import conectar
from werkzeug.security import generate_password_hash

# =========================================================
# BUSCAR USUÁRIO (Para Login)
# =========================================================
def buscar_usuario(username):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id_usuario, username, senha, nivel, ativo, data_cadastro
            FROM usuarios
            WHERE username = %s
            AND ativo = 1
        """, (username,))

        usuario = cursor.fetchone()
        cursor.close()
        return usuario
    except Exception as e:
        print(f"Erro ao buscar usuário: {e}")
        return None
    finally:
        if conn:
            conn.close()

# =========================================================
# CRIAR USUÁRIO
# =========================================================
def criar_usuario(username, senha, nivel="funcionario"):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        # Verifica se já existe
        cursor.execute("SELECT id_usuario FROM usuarios WHERE username = %s", (username,))
        if cursor.fetchone():
            raise Exception("Usuário já existe")

        senha_hash = generate_password_hash(senha)

        cursor.execute("""
            INSERT INTO usuarios (username, senha, nivel)
            VALUES (%s, %s, %s)
        """, (username, senha_hash, nivel.lower()))

        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        raise e
    finally:
        if conn:
            conn.close()

# =========================================================
# ALTERAR SENHA
# =========================================================
def alterar_senha(username, nova_senha):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        senha_hash = generate_password_hash(nova_senha)

        cursor.execute("""
            UPDATE usuarios
            SET senha = %s
            WHERE username = %s
        """, (senha_hash, username))

        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        print(f"Erro ao alterar senha: {e}")
        return False
    finally:
        if conn:
            conn.close()

# =========================================================
# LISTAR USUÁRIOS (Painel Admin)
# =========================================================
def listar_usuarios():
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id_usuario, username, nivel, ativo, data_cadastro
            FROM usuarios
            ORDER BY data_cadastro DESC
        """)

        dados = cursor.fetchall()
        cursor.close()
        return dados
    except Exception as e:
        print(f"Erro ao listar usuários: {e}")
        return []
    finally:
        if conn:
            conn.close()

# =========================================================
# ALTERAR STATUS USUÁRIO (Ativar/Desativar)
# =========================================================
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
        cursor.close()
        return True
    except Exception as e:
        print(f"Erro ao alterar status: {e}")
        return False
    finally:
        if conn:
            conn.close()

# =========================================================
# BUSCAR POR ID
# =========================================================
def buscar_usuario_id(id_usuario):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id_usuario, username, nivel, ativo, data_cadastro
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
    conn = conectar()
    cur = conn.cursor()
    cur.execute("UPDATE usuarios SET nivel = %s WHERE id = %s", (novo_nivel, id_usuario))
    conn.commit()
    conn.close()