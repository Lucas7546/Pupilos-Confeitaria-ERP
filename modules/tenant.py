from flask_login import current_user

def get_empresa_id():
    return getattr(current_user, "id_empresa", None)


def aplicar_filtro_empresa(query: str):
    empresa_id = get_empresa_id()

    if empresa_id is None:
        raise Exception("Empresa não definida no usuário")

    # padrão seguro de placeholder
    return query.replace(
        "/*empresa*/",
        f"id_empresa = {empresa_id}"
    )