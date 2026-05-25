from modules.db import conectar
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import DictCursor
from utils.logger import log_info, log_erro

# =========================
# BUSCAR USUÁRIO
# =========================
def buscar_usuario(username):
    try:
        with conectar() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("""
                    SELECT id_usuario, username, senha, nivel, ativo 
                    FROM usuarios WHERE username = %s
                """, (username.strip(),))
                return cursor.fetchone()
    except Exception as e:
        log_erro(f"Erro ao buscar usuário {username}: {e}")
        return None

# =========================
# CRIAR USUÁRIO
# =========================
def criar_usuario(username, senha, nivel="colaborador"):
    username, nivel = username.strip().lower(), nivel.strip().lower()
    niveis_validos = ["admin", "socios", "ti", "financeiro", "dono", "colaborador"]
    
    if nivel not in niveis_validos:
        log_erro(f"Tentativa de criar usuário com nível inválido: {nivel}")
        return False

    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id_usuario FROM usuarios WHERE username = %s", (username,))
                if cursor.fetchone():
                    return False
                
                cursor.execute("""
                    INSERT INTO usuarios (username, senha, nivel, ativo) 
                    VALUES (%s, %s, %s, 1)
                """, (username, generate_password_hash(senha), nivel))
                conn.commit()
                log_info(f"Usuário {username} criado com sucesso.")
                return True
    except Exception as e:
        log_erro(f"Erro ao criar usuário {username}: {e}")
        return False

# =========================
# GESTÃO DE LOGS
# =========================
def registrar_log_db(usuario, acao, modulo, detalhe):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO logs (usuario, acao, modulo, detalhe) 
                    VALUES (%s, %s, %s, %s)
                """, (usuario, acao, modulo, detalhe))
                conn.commit()
    except Exception as e:
        log_erro(f"Erro ao registrar log: {e}")

# =========================================================
# AUDITORIA - LISTAGEM PADRÃO
# =========================================================
def listar_logs_auditoria(limite=100):
    """Lista os logs mais recentes de auditoria."""
    try:
        with conectar() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("""
                    SELECT usuario, acao, modulo, detalhe, data
                    FROM logs
                    ORDER BY data DESC
                    LIMIT %s
                """, (limite,))
                return cursor.fetchall()
    except Exception as e:
        log_erro(f"Erro ao listar auditoria: {e}")
        return []

# =========================================================
# AUDITORIA - FILTRO AVANÇADO
# =========================================================
def listar_logs_auditoria_filtrado(limite=200, usuario=None, acao=None, modulo=None, data_inicio=None, data_fim=None):
    """Lista logs de auditoria aplicando filtros dinâmicos."""
    try:
        with conectar() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                query = """
                    SELECT usuario, acao, modulo, detalhe, data
                    FROM logs
                    WHERE 1=1
                """
                parametros = []

                if usuario:
                    query += " AND LOWER(usuario) LIKE LOWER(%s)"
                    parametros.append(f"%{usuario}%")
                if acao:
                    query += " AND LOWER(acao) LIKE LOWER(%s)"
                    parametros.append(f"%{acao}%")
                if modulo:
                    query += " AND LOWER(modulo) LIKE LOWER(%s)"
                    parametros.append(f"%{modulo}%")
                if data_inicio:
                    query += " AND DATE(data) >= %s"
                    parametros.append(data_inicio)
                if data_fim:
                    query += " AND DATE(data) <= %s"
                    parametros.append(data_fim)

                query += " ORDER BY data DESC LIMIT %s"
                parametros.append(limite)

                cursor.execute(query, tuple(parametros))
                return cursor.fetchall()
    except Exception as e:
        log_erro(f"Erro ao listar auditoria filtrada: {e}")
        return []

# =========================
# LISTAR USUÁRIOS
# =========================
def listar_usuarios():
    """Lista todos os usuários cadastrados."""
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id_usuario, username, nivel, ativo, data_cadastro
                    FROM usuarios
                    ORDER BY id_usuario DESC
                """)
                return cursor.fetchall()
    except Exception as e:
        log_erro(f"Erro ao listar usuários: {e}")
        return []

# =========================
# VALIDAR LOGIN
# =========================
def validar_login(username, senha):
    user = buscar_usuario(username)
    if user and user["ativo"] and check_password_hash(user["senha"], senha):
        log_info(f"Login efetuado: {username}")
        return {"id": user["id_usuario"], "username": user["username"], "nivel": user["nivel"]}
    return None

# =========================
# ALTERAR STATUS / NÍVEL / EXCLUIR
# =========================
def alterar_status(id_usuario, ativo):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE usuarios SET ativo = %s WHERE id_usuario = %s", (ativo, id_usuario))
                conn.commit()
                return True
    except Exception as e:
        log_erro(f"Erro ao alterar status usuário {id_usuario}: {e}")
        return False
            

# =========================
# BUSCAR USUÁRIO POR ID
# =========================
def buscar_usuario_id(id_usuario):
    """Busca os dados completos de um usuário pelo seu ID."""
    try:
        with conectar() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("""
                    SELECT id_usuario, username, senha, nivel, ativo, data_cadastro
                    FROM usuarios
                    WHERE id_usuario = %s
                """, (id_usuario,))
                return cursor.fetchone()
    except Exception as e:
        log_erro(f"Erro ao buscar usuário por ID {id_usuario}: {e}")
        return None

# =========================
# ATUALIZAR NÍVEL DO USUÁRIO
# =========================
def atualizar_nivel(id_usuario, novo_nivel):
    """Altera o nível de permissão de um usuário específico."""
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE usuarios 
                    SET nivel = %s 
                    WHERE id_usuario = %s
                """, (novo_nivel.lower(), id_usuario))
                conn.commit()
                log_info(f"Nível do usuário ID {id_usuario} atualizado para {novo_nivel}.")
                return True
    except Exception as e:
        log_erro(f"Erro ao atualizar nível do usuário {id_usuario}: {e}")
        return False


def excluir_usuario(id_usuario):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM usuarios WHERE id_usuario = %s", (id_usuario,))
                conn.commit()
                log_info(f"Usuário {id_usuario} excluído.")
                return True
    except Exception as e:
        log_erro(f"Erro ao excluir usuário {id_usuario}: {e}")
        return False


