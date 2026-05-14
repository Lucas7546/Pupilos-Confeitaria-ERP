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
def criar_usuario(username, senha, nivel="funcionario"):
    conn = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        username = username.strip()
        nivel = nivel.strip().lower()

        # valida nível
        if nivel not in ["admin", "gerente", "funcionario"]:
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


def excluir_usuario(id_usuario):
    conn = conectar_banco() # Sua função de conexão
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM usuarios WHERE id_usuario = %s", (id_usuario,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao excluir: {e}")
        return False
    finally:
        cur.close()
        conn.close()