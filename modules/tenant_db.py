from contextlib import contextmanager
import traceback
from flask_login import current_user
from modules.db import release_conn, get_pool
from modules.tenant import get_empresa_id


@contextmanager
def db_conn():
    conn = get_conn()

    try:
        aplicar_tenant(conn)
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        release_conn(conn)

def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    conn.autocommit = False
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
            

def aplicar_tenant(conn):
    id_empresa = get_empresa_id()

    if not id_empresa:
        return

    with conn.cursor() as cur:
        cur.execute("SET LOCAL app.id_empresa = %s", (str(id_empresa),))