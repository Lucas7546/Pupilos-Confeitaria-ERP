from contextlib import contextmanager
from modules.db import get_pool

@contextmanager
def admin_conn():

    pool = get_pool()
    conn = pool.getconn()

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        pool.putconn(conn)