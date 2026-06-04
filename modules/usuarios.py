from flask_login import current_user

from werkzeug.security import generate_password_hash, check_password_hash

from psycopg2.extras import DictCursor

from utils.logger import log_info, log_erro

from modules.db import get_conn

 



def buscar_usuario(username: str):

    try:

        with get_conn() as conn:

            with conn.cursor(cursor_factory=DictCursor) as cur:

                cur.execute(
                    """
                    SELECT
                        id_usuario,
                        username,
                        senha,
                        id_empresa,
                        nivel,
                        ativo
                    FROM usuarios
                    WHERE username = %s
                    """,
                    (username.strip(),)
                )

    user = cur.fetchone()

    return user

 

 

def buscar_usuario_id(id_usuario: int):

    try:

        with get_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                cur.execute(
                    """
                    SELECT
                        id_usuario,
                        username,
                        senha,
                        nivel,
                        id_empresa,
                        ativo,
                        data_cadastro
                    FROM usuarios
                    WHERE id_usuario = %s
                    LIMIT 1
                    """,
                    (id_usuario,)
                )

                return cur.fetchone()

    except Exception as e:
        log_erro(f"Erro ao buscar usuário ID {id_usuario}: {e}")
        return None

def criar_usuario(username: str, senha: str, nivel: str = "colaborador") -> bool:



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



        with get_conn() as conn:

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



            conn.commit()



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



        with get_conn() as conn:

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



        with get_conn() as con:

            with con.cursor() as cur:



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



            con.commit()



        return True



    except Exception as e:

        print(f"Erro ao atualizar usuário no banco: {e}")

        return False

 

 

def excluir_usuario(id_usuario: int) -> bool:



    try:



        id_empresa = current_user.id_empresa



        with get_conn() as conn:

            with conn.cursor() as cur:



                cur.execute(

                    """

                    DELETE FROM usuarios

                    WHERE id_usuario = %s

                    AND id_empresa = %s

                    """,

                    (id_usuario, id_empresa)

                )



            conn.commit()



        log_info(

            f"Usuário {id_usuario} excluído da empresa {id_empresa}"

        )



        return True



    except Exception as e:

        log_erro(f"Erro ao excluir usuário {id_usuario}: {e}")

        return False

 

 

def atualizar_nivel(id_usuario: int, novo_nivel: str) -> bool:



    try:



        id_empresa = current_user.id_empresa



        with get_conn() as conn:

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



            conn.commit()



        log_info(

            f"Nível do usuário {id_usuario} → {novo_nivel}"

        )



        return True



    except Exception as e:

        log_erro(f"Erro ao atualizar nível usuário {id_usuario}: {e}")

        return False

 

 

def registrar_log_db(
    usuario: str,
    acao: str,
    modulo: str,
    detalhe: str
) -> None:

    try:

        id_empresa = getattr(current_user, "id_empresa", None)

        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO logs
                    (
                        usuario,
                        acao,
                        modulo,
                        detalhe,
                        id_empresa
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        usuario,
                        acao,
                        modulo,
                        detalhe,
                        id_empresa
                    )
                )

            conn.commit()

    except Exception as e:
        log_erro(f"Erro ao registrar log: {e}")
 

 






