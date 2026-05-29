import os
import time
from contextlib import contextmanager
from psycopg2 import pool
 
from utils.logger import log_erro
 
# =========================================================
# POOL DE CONEXÕES
# Render free tier: limite de 25 conexões simultâneas no Postgres.
# Usamos maxconn=5 para guardar margem — o load_user do Flask-Login
# consome uma conexão por request autenticado.
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
            maxconn=5,  # Render free: 25 total; guardamos margem para outros processos
            dsn=database_url,
            sslmode="require",
        )
    return _pool
 
 
@contextmanager
def get_conn():
    """
    Context manager que pega uma conexão do pool e a devolve ao final.
 
    Se o pool estiver esgotado, tenta por até 3 segundos antes de
    lançar RuntimeError — evita que o Render derrube o processo por
    timeout enquanto espera indefinidamente.
 
    Uso:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
            conn.commit()
    """
    p = _get_pool()
    conn = None
    deadline = time.monotonic() + 3.0  # espera no máximo 3s
    while conn is None:
        try:
            conn = p.getconn()
        except pool.PoolError:
            if time.monotonic() > deadline:
                raise RuntimeError(
                    "Pool de conexões esgotado. Tente novamente em instantes."
                )
            time.sleep(0.1)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)
 
 
# Alias de compatibilidade — mantido para módulos ainda não migrados.
# O conn.close() devolve ao pool, não fecha a conexão de verdade.
def conectar():
    return _get_pool().getconn()


def init_db():
    """
    Inicializa estruturas mínimas usadas pelo app no PostgreSQL.

    As tabelas principais podem ser mantidas por migrações/scripts externos;
    aqui garantimos a tabela de logs para não derrubar o deploy no startup.
    """
    if not os.getenv("DATABASE_URL"):
        log_erro("Variável DATABASE_URL não encontrada. init_db ignorado.")
        return

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id_log SERIAL PRIMARY KEY,
                    usuario TEXT,
                    acao TEXT,
                    modulo TEXT,
                    detalhe TEXT,
                    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        conn.commit()
