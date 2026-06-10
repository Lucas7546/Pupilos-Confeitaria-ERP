from contextlib import contextmanager

from flask_login import current_user

from modules.db import ( get_conn as base_get_conn, release_conn)

from modules.tenant import get_empresa_id


@contextmanager
def db_conn():
    conn = get_conn()

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        print("DEVOLVEU CONEXAO")
        release_conn(conn)


def get_conn():
    print("TENANT_DB GET_CONN")

    conn = base_get_conn()

    try:
        if (
            hasattr(current_user, "is_authenticated")
            and current_user.is_authenticated
            and getattr(current_user, "id_empresa", None)
        ):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT set_config(
                        'app.id_empresa',
                        %s,
                        false
                    )
                    """,
                    (str(current_user.id_empresa),)
                )

    except Exception:
        pass

    return conn


def execute_secure(query, params=(), fetch=False):
    id_empresa = get_empresa_id()

    with db_conn() as conn:
        with conn.cursor() as cur:

            if isinstance(params, dict):
                params["id_empresa"] = id_empresa

            elif params is None:
                params = [id_empresa]

            elif isinstance(params, (list, tuple)):
                params = list(params)
                params.append(id_empresa)

            cur.execute(query, params)

            if fetch:
                return cur.fetchall()