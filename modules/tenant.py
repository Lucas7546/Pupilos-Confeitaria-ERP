from flask import g
from flask_login import current_user
from modules.tenant_db import get_conn as tenant_conn


# =========================================================
# CONTEXTO DA EMPRESA (REQUEST)
# =========================================================
def set_empresa_context():
    """
    Executado no before_request
    Define a empresa ativa do usuário logado
    """

    if current_user.is_authenticated:
        g.id_empresa = getattr(current_user, "id_empresa", None)
    else:
        g.id_empresa = None


# =========================================================
# PEGAR EMPRESA ATUAL (FONTE ÚNICA)
# =========================================================
def get_empresa_id():
    """
    Fonte única do id_empresa atual.
    """

    id_empresa = getattr(g, "id_empresa", None)

    if id_empresa is None:
        raise PermissionError("Acesso negado: id_empresa não identificado no contexto.")

    return id_empresa


# =========================================================
# FILTRO PADRÃO SQL
# =========================================================
def aplicar_filtro_empresa(sql: str, params=(), alias: str = ""):

    id_empresa = get_empresa_id()

    campo = f"{alias}.id_empresa" if alias else "id_empresa"

    sql = sql.replace(
        "/*empresa*/",
        f"{campo} = %s"
    )

    return sql, (*params, id_empresa)


# =========================================================
# QUERY SEGURA (LEGADO CONTROLADO)
# =========================================================
def query_empresa(cur, sql, params=(), alias=""):

    id_empresa = get_empresa_id()

    campo = f"{alias}.id_empresa" if alias else "id_empresa"

    if "WHERE" in sql.upper():
        sql += f" AND {campo} = %s"
    else:
        sql += f" WHERE {campo} = %s"

    cur.execute(sql, (*params, id_empresa))
    return cur.fetchall()


# =========================================================
# EXECUTOR SEGURO
# =========================================================
def execute_secure(query, params=(), fetch=False):

    id_empresa = get_empresa_id()

    with tenant_conn() as conn:
        with conn.cursor() as cur:

            if isinstance(params, dict):
                params["id_empresa"] = id_empresa

            cur.execute(query, params)

            if fetch:
                return cur.fetchall()

            conn.commit()