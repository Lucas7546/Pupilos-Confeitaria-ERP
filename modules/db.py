import os
import time
from psycopg2 import pool

_pool = None


def _get_pool():
    global _pool

    if _pool is None or _pool.closed:
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise RuntimeError("DATABASE_URL não encontrada")

        if "sslmode" not in database_url:
            database_url += "?sslmode=require"

        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=database_url
        )

    return _pool


def query(sql, params=()):
    pool = _get_pool()
    conn = pool.getconn()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    finally:
        pool.putconn(conn)


def conectar():
    return _get_pool().getconn()