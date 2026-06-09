from flask import g, request
from flask_login import current_user
from modules.tenant_db import get_conn as tenant_conn


# =========================================================
# CONTEXTO DA EMPRESA (ÚNICO)
# =========================================================
IGNORAR = ["/static", "/favicon.ico"]

def set_empresa_context():
    path = request.path

    if any(path.startswith(p) for p in IGNORAR):
        return

    g.id_empresa = None

    try:
        if current_user.is_authenticated:
            g.id_empresa = getattr(current_user, "id_empresa", None)
    except Exception:
        g.id_empresa = None

# =========================================================
# GET PADRÃO
# =========================================================
def get_empresa_id():

    id_empresa = getattr(g, "id_empresa", None)

    if not id_empresa:
        raise Exception("Tenant não definido")

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

def get_empresa_id_safe():
    return getattr(g, "id_empresa", None)