from contextlib import contextmanager
import traceback
from flask_login import current_user
from modules.db import get_pool
from modules.tenant import get_empresa_id


@contextmanager
def db_conn():
    conn = get_pool().getconn()
    conn.autocommit = False

    try:
        from flask import has_request_context, g

        id_empresa = None

        if has_request_context():
            id_empresa = getattr(g, "id_empresa", None)

        if id_empresa:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL app.id_empresa = %s", (str(id_empresa),))

        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        get_pool().putconn(conn)

def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    conn.autocommit = False
    return conn


def execute_secure(query, params=(), fetch=False):
    id_empresa = get_empresa_id(strict=False)

    if not id_empresa:
        raise Exception("Tenant obrigatório")

    with db_conn(with_tenant=True) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)

            if fetch:
                return cur.fetchall()
            

def aplicar_tenant(conn):
    id_empresa = get_empresa_id(strict=False)

    if not id_empresa:
        return  # login / contexto público

    with conn.cursor() as cur:
        cur.execute("SET LOCAL app.id_empresa = %s", (str(id_empresa),))

@contextmanager
def db_admin_conn():
    conn = get_pool().getconn()
    conn.autocommit = False  # Importante para manter o padrão
    try:
        # Aqui NENHUM 'SET LOCAL' é executado. 
        # Portanto, o RLS não terá um 'app.id_empresa' para filtrar.
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        get_pool().putconn(conn)