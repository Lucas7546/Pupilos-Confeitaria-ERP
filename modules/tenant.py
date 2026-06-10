from flask import g, request, session, g, has_request_context
from flask_login import current_user
from modules.tenant_db import get_conn as tenant_conn

EXCLUIR_PATHS = ["/static", "/favicon.ico", "/login"]

def set_empresa_context():
    if current_user.is_authenticated:
        g.id_empresa = current_user.id_empresa
# =========================================================
# GET PADRÃO
# =========================================================
def get_empresa_id():
    if has_request_context():
        id_empresa = getattr(g, "id_empresa", None)

        if id_empresa:
            return id_empresa

        if session.get("id_empresa"):
            return session.get("id_empresa")

    if current_user and current_user.is_authenticated:
        return current_user.id_empresa

    raise Exception("Tenant não definido")

# =========================================================
# FILTRO PADRÃO SQL
# =========================================================
def aplicar_filtro_empresa(sql: str, params=(), alias: str = ""):

    id_empresa = get_empresa_id()

    campo = f"{alias}.id_empresa" if alias else "id_empresa"

    sql = sql.replace(
        "/*empresa*/",
        f"{campo} = %s" )

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

            elif params is None:
                 params = [id_empresa]
            elif isinstance(params, (list, tuple)):
                params = list(params)
                params.append(id_empresa)

            cur.execute(query, params)

            if fetch:
                return cur.fetchall()

            conn.commit()

def get_empresa_id_safe():
    return getattr(g, "id_empresa", None)