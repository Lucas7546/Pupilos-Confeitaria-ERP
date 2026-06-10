from contextlib import contextmanager
from modules.db import get_conn, release_conn
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
        release_conn(conn)


@contextmanager
def tenant_conn():
    conn = get_conn()
    id_empresa = get_empresa_id()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.id_empresa', %s, false)",
                (str(id_empresa),)
            )

        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        release_conn(conn)

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
            conn.commit()