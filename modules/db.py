import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool

from utils.logger import log_erro

# =========================================================
# POOL DE CONEXÕES
# Cria o pool uma única vez na inicialização do processo.
# Isso elimina o custo de abrir/fechar conexão a cada request
# e evita esgotar os conexões do Render (limite 25 no free tier).
# =========================================================
_pool: pool.ThreadedConnectionPool | None = None


def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("Variável DATABASE_URL não encontrada.")
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=database_url,
            sslmode="require",
        )
    return _pool


@contextmanager
def get_conn():
    """
    Context manager que pega uma conexão do pool e a devolve ao final.
    Uso obrigatório em todo o código:

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
            conn.commit()

    Em caso de exceção o rollback é feito automaticamente antes de
    devolver a conexão ao pool, evitando conexões em estado sujo.
    """
    p = _get_pool()
    conn = p.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)


# Alias de compatibilidade para o código antigo que ainda usa `conectar()`.
# Vai sendo removido à medida que cada módulo migrar para `get_conn()`.
def conectar():
    """
    DEPRECADO — prefira `get_conn()`.
    Mantido apenas para não quebrar módulos ainda não migrados.
    Retorna uma conexão raw do pool; o chamador é responsável por
    chamar conn.close() (que devolve ao pool, não fecha de verdade).
    """
    return _get_pool().getconn()