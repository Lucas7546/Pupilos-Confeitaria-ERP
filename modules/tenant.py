from flask_login import current_user
from flask import g


def get_empresa_id():
    return getattr(current_user, "id_empresa", None)


def query_empresa(cur, sql, params=()):

    empresa_id = get_empresa_id()

    if empresa_id is None:
        raise Exception("Empresa não definida")

    sql = sql.replace(
        "/*empresa*/",
        "id_empresa = %s"
    )

    cur.execute(
        sql,
        (*params, empresa_id)
    )

    return cur.fetchall()


def aplicar_filtro_empresa(query: str):

    empresa_id = get_empresa_id()

    if empresa_id is None:
        raise Exception("Empresa não definida")

    return query.replace(
        "/*empresa*/",
        f"id_empresa = {int(empresa_id)}"
    )