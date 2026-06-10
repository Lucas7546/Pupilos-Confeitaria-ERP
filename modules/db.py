import os
from psycopg2 import pool

_pool = None


def get_pool():
    global _pool

    if _pool is None or _pool.closed:
        db_url = os.getenv("DATABASE_URL")

        if not db_url:
            raise RuntimeError("DATABASE_URL não encontrada")

        if "sslmode" not in db_url:
            db_url += "?sslmode=require"

        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=15,
            dsn=db_url
        )

    return _pool


def get_conn():
    print("DB GET_CONN")
    conn = get_pool().getconn()
    conn.autocommit = False
    return conn


def release_conn(conn):
    print("DEVOLVEU CONEXAO")
    get_pool().putconn(conn)