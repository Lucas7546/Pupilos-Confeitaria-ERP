from flask import g
from flask_login import current_user, AnonymousUserMixin



__all__ = ["get_empresa_id"]


def get_empresa_id(strict=True):
    if hasattr(g, "id_empresa") and g.id_empresa:
        return g.id_empresa

    if current_user and getattr(current_user, "is_authenticated", False):
        return current_user.id_empresa

    if strict:
        return None  # 👈 NÃO quebra login
    return None
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

def get_empresa_id_login(user_data):
    return user_data["id_empresa"]

def safe_execute(cur, sql, params):
    if "%s" in sql and (not params or len(params) == 0):
        raise Exception("QUERY SEM PARAMETRO DE TENANT")

    cur.execute(sql, params)