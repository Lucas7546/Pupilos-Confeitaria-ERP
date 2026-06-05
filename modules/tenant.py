from flask_login import current_user


def get_empresa_id():

    empresa_id = getattr(current_user, "id_empresa", None)

    if empresa_id is None:
        raise PermissionError(
            "Acesso negado: Empresa não identificada na sessão."
        )

    return empresa_id


def query_empresa(cur, sql, params=(), alias=""):
    """
    Compatibilidade com código legado.
    Evite utilizar em novas implementações.
    """

    empresa_id = get_empresa_id()

    campo = (
        f"{alias}.id_empresa"
        if alias
        else "id_empresa"
    )

    if "WHERE" in sql.upper():
        sql += f" AND {campo} = %s"
    else:
        sql += f" WHERE {campo} = %s"

    cur.execute(sql, (*params, empresa_id))

    return cur.fetchall()


def aplicar_filtro_empresa(
    sql: str,
    params=(),
    alias: str = ""
):
    """
    Forma recomendada para novas consultas.

    Exemplo:

        sql, params = aplicar_filtro_empresa(
            '''
            SELECT *
            FROM produtos p
            WHERE /*empresa*/
            ''',
            alias="p"
        )

        cur.execute(sql, params)
    """

    empresa_id = get_empresa_id()

    campo = (
        f"{alias}.id_empresa"
        if alias
        else "id_empresa"
    )

    sql = sql.replace(
        "/*empresa*/",
        f"{campo} = %s"
    )

    return sql, (*params, empresa_id)


def formatar_query_empresa(sql: str) -> str:
    """
    LEGADO.

    Utilize somente quando realmente não for possível
    trabalhar com parâmetros SQL.

    Prefira sempre aplicar_filtro_empresa().
    """

    empresa_id = get_empresa_id()

    return sql.replace(
        "/*empresa*/",
        f"id_empresa = {int(empresa_id)}"
    )