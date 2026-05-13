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

        # Removi o "AND ativo = 1" para permitir que o sistema identifique 
        # usuários bloqueados e mande a mensagem correta no login
        cursor.execute("""
            SELECT id_usuario, username, senha, nivel, ativo, data_cadastro
            FROM usuarios
            WHERE username = %s
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

        # Se a senha já vier com hash do app.py, não gera de novo. 
        # Se vier texto puro, gera o hash.
        if not senha.startswith('pbkdf2:sha256:'):
            senha_hash = generate_password_hash(senha)
        else:
            senha_hash = senha

        cursor.execute("""
            INSERT INTO usuarios (username, senha, nivel, ativo)
            VALUES (%s, %s, %s, 1)
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

# =========================================================
# LISTAR USUÁRIOS E STATUS
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