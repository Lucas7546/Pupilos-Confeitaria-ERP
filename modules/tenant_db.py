from contextlib import contextmanager
from modules.db import get_conn, release_conn, get_pool
from modules.tenant import get_empresa_id
from flask_login import current_user


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
        release_conn(conn)


def get_conn():
    conn = get_pool().getconn()
    conn.autocommit = False

    try:
        if current_user.is_authenticated:
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
    except:
        pass

    return conn

# =========================================================
# EXECUTOR SEGURO
# =========================================================
def execute_secure(query, params=(), fetch=False):
    id_empresa = get_empresa_id()

    with get_conn() as conn:
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