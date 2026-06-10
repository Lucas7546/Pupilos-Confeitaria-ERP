from flask_login import current_user
from flask import g




__all__ = ["get_empresa_id", "set_empresa_context"]


def get_empresa_id():
    """
    Fonte única e segura de tenant.
    Ordem de prioridade:
    1. g (request context)
    2. current_user
    """

    id_empresa = getattr(g, "id_empresa", None)

    if id_empresa:
        return id_empresa

    if current_user and current_user.is_authenticated:
        return getattr(current_user, "id_empresa", None)

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


            

def set_empresa_context():
    if current_user.is_authenticated:
        g.id_empresa = current_user.id_empresa