from flask import g, flash, redirect, url_for
from modules.tenant_db import db_conn
from functools import wraps
from utils.logger import log_erro


def get_plano_empresa():

    try:

        id_empresa = getattr(g, "id_empresa", None)

        if id_empresa is None:
            return "basic"

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT plano
                    FROM empresa_planos
                    WHERE id_empresa = %s
                    AND ativo = TRUE
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (id_empresa,)
                )

                row = cur.fetchone()

        if not row:
            return "basic"

        return row[0]

    except Exception as e:

        log_erro(
            f"Erro ao obter plano da empresa: {e}"
        )

        return "basic"

def plano_requerido(plano_minimo):

    ordem = {
        "basic": 1,
        "premium": 2
    }

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            try:

                plano = get_plano_empresa()

                if ordem.get(plano, 0) < ordem.get(plano_minimo, 0):

                    flash(
                        "Seu plano não permite acessar essa funcionalidade.",
                        "warning"
                    )

                    return redirect(
                        url_for("main.dashboard")
                    )

                return func(*args, **kwargs)

            except Exception as e:

                log_erro(
                    f"Erro na validação de plano: {e}"
                )

                flash(
                    "Erro ao validar seu plano.",
                    "danger"
                )

                return redirect(
                    url_for("main.dashboard")
                )

        return wrapper

    return decorator