from flask import g, flash, redirect, url_for
from modules.tenant_db import db_conn
from functools import wraps
from utils.logger import log_erro


PLANOS_ORDEM = {
    "starter": 1,
    "pro": 2,
    "enterprise": 3
}


def get_plano_empresa():

    try:

        id_empresa = getattr(g, "id_empresa", None)

        if id_empresa is None:
            return "starter"

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT plano
                    FROM empresa_planos
                    WHERE id_empresa = %s
                    AND ativo = 1
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (id_empresa,)
                )

                row = cur.fetchone()

        if not row:
            return "starter"

        return row[0]

    except Exception as e:

        log_erro(
            f"Erro ao obter plano da empresa: {e}"
        )

        return "starter"

def plano_requerido(plano_minimo):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                plano_atual = get_plano_empresa()
                nivel_atual = PLANOS_ORDEM.get(plano_atual, 0)
                nivel_exigido = PLANOS_ORDEM.get(plano_minimo, 0)

                if nivel_atual < nivel_exigido:
                    flash(f"Este recurso exige o plano {plano_minimo.upper()} ou superior.", "warning")
                    return redirect(url_for("empresas.upgrade", recurso=func.__name__))
                
                return func(*args, **kwargs)
            except Exception as e:
                log_erro(f"Erro no decorador de plano: {e}")
                flash("Erro ao verificar permissões.", "danger")
                return redirect(url_for("main.dashboard"))
        return wrapper
    return decorator