from modules.db import _get_pool
from flask import g
from contextlib import contextmanager
from flask_login import current_user
from modules.tenant import get_empresa_id

@contextmanager
def get_conn():

    id_empresa = get_empresa_id()

    pool = _get_pool()
    conn = pool.getconn()

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
        pool.putconn(conn)