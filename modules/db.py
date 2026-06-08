import os
import time
from contextlib import contextmanager
from psycopg2 import pool

_pool = None

def _get_pool():
    global _pool

    if _pool is None or _pool.closed:
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise RuntimeError("DATABASE_URL não encontrada no ambiente")

        # força SSL (Supabase exige em muitos casos)
        if "sslmode" not in database_url:
            database_url += "?sslmode=require"

        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=database_url
        )

    return _pool


@contextmanager
def get_conn():
    p = _get_pool()
    conn = None

    deadline = time.monotonic() + 5

    while conn is None:
        try:
            conn = p.getconn()
        except Exception:
            if time.monotonic() > deadline:
                raise RuntimeError("Pool de conexões esgotado")
            time.sleep(0.5)

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


def query(sql, params=()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
 
# Alias de compatibilidade — mantido para módulos ainda não migrados.
# O conn.close() devolve ao pool, não fecha a conexão de verdade.
def conectar():
    return _get_pool().getconn()
