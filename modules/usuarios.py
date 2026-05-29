
from modules.db import get_conn
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import DictCursor
from utils.logger import log_info, log_erro
 
 
def buscar_usuario(username: str):
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    "SELECT id_usuario, username, senha, nivel, ativo FROM usuarios WHERE username = %s",
                    (username.strip(),),
                )
                return cur.fetchone()
    except Exception as e:
        log_erro(f"Erro ao buscar usuário {username}: {e}")
        return None
 
 
def buscar_usuario_id(id_usuario: int):
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    "SELECT id_usuario, username, senha, nivel, ativo, data_cadastro FROM usuarios WHERE id_usuario = %s",
                    (id_usuario,),
                )
                return cur.fetchone()
    except Exception as e:
        log_erro(f"Erro ao buscar usuário ID {id_usuario}: {e}")
        return None
 
 
def criar_usuario(username: str, senha: str, nivel: str = "colaborador") -> bool:
    username = username.strip().lower()
    nivel    = nivel.strip().lower()
    niveis_validos = ["admin", "socios", "ti", "financeiro", "dono", "colaborador"]
 
    if nivel not in niveis_validos:
        log_erro(f"Nível inválido ao criar usuário: {nivel}")
        return False
 
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id_usuario FROM usuarios WHERE username = %s", (username,))
                if cur.fetchone():
                    return False
                cur.execute(
                    "INSERT INTO usuarios (username, senha, nivel, ativo) VALUES (%s,%s,%s,1)",
                    (username, generate_password_hash(senha), nivel),
                )
            conn.commit()
        log_info(f"Usuário '{username}' criado.")
        return True
    except Exception as e:
        log_erro(f"Erro ao criar usuário '{username}': {e}")
        return False
 
 
def listar_usuarios() -> list:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id_usuario, username, nivel, ativo, data_cadastro FROM usuarios ORDER BY id_usuario DESC"
                )
                return cur.fetchall()
    except Exception as e:
        log_erro(f"Erro ao listar usuários: {e}")
        return []
 
 
def alterar_status(id_usuario: int, ativo: int) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE usuarios SET ativo=%s WHERE id_usuario=%s", (ativo, id_usuario))
            conn.commit()
        return True
    except Exception as e:
        log_erro(f"Erro ao alterar status usuário {id_usuario}: {e}")
        return False
 
 
def excluir_usuario(id_usuario: int) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM usuarios WHERE id_usuario=%s", (id_usuario,))
            conn.commit()
        log_info(f"Usuário {id_usuario} excluído.")
        return True
    except Exception as e:
        log_erro(f"Erro ao excluir usuário {id_usuario}: {e}")
        return False
 
 
def atualizar_nivel(id_usuario: int, novo_nivel: str) -> bool:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE usuarios SET nivel=%s WHERE id_usuario=%s",
                    (novo_nivel.lower(), id_usuario),
                )
            conn.commit()
        log_info(f"Nível do usuário {id_usuario} → {novo_nivel}")
        return True
    except Exception as e:
        log_erro(f"Erro ao atualizar nível usuário {id_usuario}: {e}")
        return False
 
 
def registrar_log_db(usuario: str, acao: str, modulo: str, detalhe: str) -> None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO logs (usuario, acao, modulo, detalhe) VALUES (%s,%s,%s,%s)",
                    (usuario, acao, modulo, detalhe),
                )
            conn.commit()
    except Exception as e:
        log_erro(f"Erro ao registrar log: {e}")
 
 
def validar_login(username: str, senha: str):
    user = buscar_usuario(username)
    if user and user["ativo"] and check_password_hash(user["senha"], senha):
        log_info(f"Login: {username}")
        return {"id": user["id_usuario"], "username": user["username"], "nivel": user["nivel"]}
    return None

def atualizar_usuario(id_usuario, nivel, nova_senha=None):
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                if nova_senha:
                    query = "UPDATE usuarios SET nivel=%s, senha=%s WHERE id_usuario=%s"
                    params = (nivel, generate_password_hash(nova_senha), id_usuario)
                else:
                    query = "UPDATE usuarios SET nivel=%s WHERE id_usuario=%s"
                    params = (nivel, id_usuario)
                
                cur.execute(query, params)
            con.commit()
            return True
    except Exception as e:
        print(f"Erro ao atualizar usuário no banco: {e}")
        return False

def alterar_status(id_usuario, novo_status):
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    "UPDATE usuarios SET ativo = %s WHERE id_usuario = %s",
                    (novo_status, id_usuario)
                )
            con.commit()
            return True
    except Exception as e:
        print(f"Erro ao alterar status no Postgres: {e}")
        return False