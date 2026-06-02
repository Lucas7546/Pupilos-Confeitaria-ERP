from flask_login import current_user

def get_empresa_id():
    return getattr(current_user, "id_empresa", None)

def query_empresa(cur, sql, params=()):
    empresa_id = getattr(g, "empresa_id", None)

    if empresa_id is None:
        raise Exception("Sem empresa no contexto (g.empresa_id)")

    sql = sql.replace("/*empresa*/", "id_empresa = %s")

    cur.execute(sql, (*params, empresa_id))
    return cur.fetchall()

def aplicar_filtro_empresa(query: str):
    empresa_id = get_empresa_id()

    if empresa_id is None:
        raise Exception("Empresa não definida no usuário")

    # padrão seguro de placeholder
    return query.replace(
        "/*empresa*/",
        f"id_empresa = {empresa_id}"
    )