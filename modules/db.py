import os
import time
from contextlib import contextmanager
from psycopg2 import pool
from flask import g
import logging
 
# =========================================================
# POOL DE CONEXÕES
# =========================================================
_pool: pool.ThreadedConnectionPool | None = None





def query(sql, params=()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() 
 
def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("Variável DATABASE_URL não encontrada.")
        
        # FIX: O Supabase recomenda usar a porta 6543 (Transaction Pooler)
        # Se sua URL ainda estiver com 5432, altere para 6543
        if ":5432/" in database_url:
            database_url = database_url.replace(":5432/", ":6543/")
            
        # Adicionar o parâmetro para forçar IPv4 se necessário
        # Algumas versões do psycopg2 aceitam 'options' para forçar o IP
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=database_url,
            # Remova o sslmode daqui se ele já estiver na sua DATABASE_URL
            # Se você usa dsn=url, o sslmode deve estar na string da URL
        )
    return _pool
 
 
@contextmanager
def get_conn():
    p = _get_pool()
    conn = None
    deadline = time.monotonic() + 5.0  # Aumentei para 5s, rede instável no Render
    while conn is None:
        try:
            conn = p.getconn()
        except Exception: # Captura erro de pool genérico
            if time.monotonic() > deadline:
                raise RuntimeError("Pool de conexões esgotado.")
            time.sleep(0.5)
    try:
        yield conn
        conn.commit() # Adicionei o commit automático aqui para simplificar
    except Exception:
        conn.rollback()
        raise
    finally:
        p.putconn(conn)
 
 
# Alias de compatibilidade — mantido para módulos ainda não migrados.
# O conn.close() devolve ao pool, não fecha a conexão de verdade.
def conectar():
    return _get_pool().getconn()
