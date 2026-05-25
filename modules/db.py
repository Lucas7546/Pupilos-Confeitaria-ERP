import os
from contextlib import contextmanager
from psycopg2 import pool
from utils.logger import log_erro

_pool = None


def _get_pool():
    global _pool

    if _pool is None or _pool.closed:
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise RuntimeError("DATABASE_URL não encontrada")

        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,  # seguro para Render
            dsn=database_url,
            sslmode="require"
        )

    return _pool


# =========================================================
# 🧠 MODO SEGURO (NOVO PADRÃO)
# =========================================================
@contextmanager
def get_conn():
    conn = None
    try:
        conn = _get_pool().getconn()
        yield conn
        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        log_erro(f"DB ERROR: {e}")
        raise

    finally:
        if conn:
            _get_pool().putconn(conn)


# =========================================================
# 🔥 COMPATIBILIDADE TOTAL (NÃO QUEBRA NADA)
# =========================================================
def conectar():
    """
    LEGACY SAFE:
    mantém compatibilidade com TODO seu app antigo.
    NÃO remove isso ainda.
    """
    return _get_pool().getconn()


# =========================================================
# 🧹 FUNÇÃO EXTRA (OPCIONAL, AJUDA A EVITAR VAZAMENTO)
# =========================================================
def devolver_conexao(conn):
    """
    Use isso em códigos antigos se quiser corrigir aos poucos.
    """
    try:
        if conn:
            _get_pool().putconn(conn)
    except Exception as e:
        log_erro(f"Erro ao devolver conexão: {e}")
    

def devolver(conn):
    """
    Substitui o 'close()' problemático.
    """
    try:
        _get_pool().putconn(conn)
    except Exception as e:
        log_erro("POOL_RETURN_ERROR", str(e))