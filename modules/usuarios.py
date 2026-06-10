from flask_login import current_user

from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import DictCursor, RealDictCursor
from functools import lru_cache
from utils.logger import log_info, log_erro
from modules.tenant_db import get_conn, db_conn
from modules.db import release_conn


def buscar_usuario_global(id_usuario: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT
                    id_usuario,
                    username,
                    nivel,
                    id_empresa,
                    ativo,
                    is_superadmin
                FROM usuarios
                WHERE id_usuario = %s
                LIMIT 1
            """, (id_usuario,))

            return cur.fetchone()

    finally:
        release_conn(conn)

@lru_cache(maxsize=1024)
def buscar_usuario_global_cached(id_usuario: int):
    return buscar_usuario_global(id_usuario)

def buscar_usuario(username: str):
    try:
        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT
                        id_usuario,
                        username,
                        senha,
                        nivel,
                        id_empresa,
                        ativo,
                        is_superadmin
                    FROM usuarios
                    WHERE username = %s
                    LIMIT 1
                """, (username.strip(),))

                return cur.fetchone()

    except Exception as e:
        log_erro(f"Erro ao buscar usuário {username}: {e}")
        return None

 

 

def buscar_usuario_id(id_usuario: int):
    try:
        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT
                        id_usuario,
                        username,
                        nivel,
                        id_empresa,
                        ativo,
                        is_superadmin,
                        data_cadastro
                    FROM usuarios
                    WHERE id_usuario = %s
                    LIMIT 1
                """, (id_usuario,))

                return cur.fetchone()

    except Exception as e:
        log_erro(f"Erro ao buscar usuário ID {id_usuario}: {e}")
        return None

def criar_usuario(username: str, senha: str, nivel: str = "colaborador") -> bool:

    if current_user.nivel == "dono" and nivel.lower() == "admin":
        return False

    username = username.strip().lower()

    nivel = nivel.strip().lower()



    niveis_validos = [

        "admin",

        "socios",

        "ti",

        "financeiro",

        "dono",

        "colaborador"

    ]



    if nivel not in niveis_validos:

        log_erro(f"Nível inválido ao criar usuário: {nivel}")

        return False



    try:



        id_empresa = current_user.id_empresa



        with db_conn() as conn:

            with conn.cursor() as cur:



                cur.execute(

                    """

                    SELECT id_usuario

                    FROM usuarios

                    WHERE username = %s

                    AND id_empresa = %s

                    """,

                    (username, id_empresa)

                )



                if cur.fetchone():

                    return False



                cur.execute(

                    """

                    INSERT INTO usuarios

                    (

                        username,

                        senha,

                        nivel,

                        ativo,

                        id_empresa

                    )

                    VALUES

                    (

                        %s,

                        %s,

                        %s,

                        1,

                        %s

                    )

                    """,

                    (

                        username,

                        generate_password_hash(senha),

                        nivel,

                        id_empresa

                    )

                )

        log_info(

            f"Usuário '{username}' criado para empresa {id_empresa}"

        )
        return True
    except Exception as e:
        log_erro(f"Erro ao criar usuário '{username}': {e}")
        return False

def listar_usuarios():

    try:
        id_empresa = current_user.id_empresa

        with db_conn() as conn:

            with conn.cursor() as cur:



                cur.execute(

                    """

                    SELECT

                        id_usuario,

                        username,

                        nivel,

                        ativo,

                        data_cadastro

                    FROM usuarios

                    WHERE id_empresa = %s

                    ORDER BY id_usuario DESC

                    """,

                    (id_empresa,)

                )



                return cur.fetchall()
    except Exception as e:

        log_erro(f"Erro ao listar usuários: {e}")

        return []

def atualizar_usuario(

    id_usuario,

    nivel,

    nova_senha=None

):



    try:



        id_empresa = current_user.id_empresa



        with db_conn() as conn:

            with conn.cursor() as cur:



                if nova_senha:



                    cur.execute(

                        """

                        UPDATE usuarios

                        SET nivel = %s,

                            senha = %s

                        WHERE id_usuario = %s

                        AND id_empresa = %s

                        """,

                        (

                            nivel,

                            generate_password_hash(nova_senha),

                            id_usuario,

                            id_empresa

                        )

                    )



                else:



                    cur.execute(

                        """

                        UPDATE usuarios

                        SET nivel = %s

                        WHERE id_usuario = %s

                        AND id_empresa = %s

                        """,

                        (

                            nivel,

                            id_usuario,

                            id_empresa

                        )

                    )
        return True
    except Exception as e:

        print(f"Erro ao atualizar usuário no banco: {e}")

        return False

def excluir_usuario(id_usuario: int) -> bool:

    # 1. Busca quem é o alvo primeiro
    usuario_alvo = buscar_usuario_id(id_usuario, current_user.id_empresa)
    if not usuario_alvo: return False
    
    # 2. Regra: O dono não pode excluir o ADMIN (você)
    if usuario_alvo['nivel'] == 'admin':
        return False
        
    # 3. Regra: O dono não pode se excluir (opcional, mas recomendado)
    if int(id_usuario) == int(current_user.id):
        return False

    try:



        id_empresa = current_user.id_empresa



        with db_conn() as conn:

            with conn.cursor() as cur:



                cur.execute(

                    """

                    DELETE FROM usuarios

                    WHERE id_usuario = %s

                    AND id_empresa = %s

                    """,

                    (id_usuario, id_empresa)

                )







        log_info(

            f"Usuário {id_usuario} excluído da empresa {id_empresa}"

        )



        return True



    except Exception as e:

        log_erro(f"Erro ao excluir usuário {id_usuario}: {e}")

        return False

 

 

def atualizar_nivel(id_usuario: int, novo_nivel: str) -> bool:

    # --- BLOQUEIO DE SEGURANÇA ---
    # 1. Ninguém vira admin, exceto se já for admin
    if novo_nivel.lower() == 'admin' and current_user.nivel != 'admin':
        return False
        
    # 2. Impedir que o dono tente alterar o Admin (você)
    usuario_alvo = buscar_usuario_id(id_usuario, current_user.id_empresa)
    if usuario_alvo and usuario_alvo['nivel'] == 'admin' and current_user.nivel != 'admin':
        return False
    # -----------------------------


    try:



        id_empresa = current_user.id_empresa



        with db_conn() as conn:

            with conn.cursor() as cur:



                cur.execute(

                    """

                    UPDATE usuarios

                    SET nivel = %s

                    WHERE id_usuario = %s

                    AND id_empresa = %s

                    """,

                    (

                        novo_nivel.lower(),

                        id_usuario,

                        id_empresa

                    )

                )






        log_info(

            f"Nível do usuário {id_usuario} → {novo_nivel}"

        )



        return True



    except Exception as e:

        log_erro(f"Erro ao atualizar nível usuário {id_usuario}: {e}")

        return False

 

 

def registrar_log_db(usuario: str, acao: str, modulo: str, detalhe: str) -> None:
    try:
        # Força o id_empresa para 0 se o usuário for superadmin (ou não tiver empresa)
        id_empresa = getattr(current_user, "id_empresa", 0) or 0 
        
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO logs (usuario, acao, modulo, detalhe, id_empresa)
                    VALUES (%s, %s, %s, %s, %s)
                """, (usuario, acao, modulo, detalhe, id_empresa))
    except Exception as e:
        log_erro(f"Erro ao registrar log: {e}")



def criar_usuario_empresa(
    username,
    senha,
    nivel,
    id_empresa,
    conn=None
):

    senha_hash = generate_password_hash(senha)

    if conn:

        with conn.cursor() as cur:

            cur.execute("""
                INSERT INTO usuarios
                (
                    username,
                    senha,
                    nivel,
                    ativo,
                    id_empresa
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    1,
                    %s
                )
            """,
            (
                username.lower().strip(),
                senha_hash,
                nivel,
                id_empresa
            ))

    else:

        with db_conn() as conn:

            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO usuarios
                    (
                        username,
                        senha,
                        nivel,
                        ativo,
                        id_empresa
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        1,
                        %s
                    )
                """,
                (
                    username.lower().strip(),
                    senha_hash,
                    nivel,
                    id_empresa
                ))

    return True
 

def alterar_status(id_usuario: int, novo_status: int) -> bool:
    try:
        id_empresa = current_user.id_empresa
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE usuarios 
                    SET ativo = %s 
                    WHERE id_usuario = %s AND id_empresa = %s
                """, (novo_status, id_usuario, id_empresa))
        return True
    except Exception as e:
        log_erro(f"Erro ao alterar status do usuário {id_usuario}: {e}")
        return False
    







