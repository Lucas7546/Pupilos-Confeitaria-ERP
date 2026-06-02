from flask import g, flash, redirect, url_for
from modules.db import get_conn
from functools import wraps


def get_plano_empresa():
    empresa_id = getattr(g, "empresa_id", None)

    if not empresa_id:
        return "basic"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT plano
                FROM empresa_planos
                WHERE id_empresa = %s
                AND ativo = TRUE
                ORDER BY id DESC
                LIMIT 1
            """, (empresa_id,))
            row = cur.fetchone()

    return row[0] if row else "basic"

def plano_requerido(plano_minimo):
    
    ordem = {
        "basic": 1,
        "premium": 2
    }

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            plano = get_plano_empresa()

            if ordem.get(plano, 0) < ordem.get(plano_minimo, 0):
                flash("Seu plano não permite acessar essa funcionalidade.", "warning")
                return redirect(url_for("main.dashboard"))

            return func(*args, **kwargs)

        return wrapper

    return decorator