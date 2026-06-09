from flask import g
from flask_login import current_user
from modules.tenant_db import get_conn


# =========================================================
# CONTEXTO DA EMPRESA (REQUEST)
# =========================================================
def set_empresa_context():
    """
    Executado no before_request
    Define a empresa ativa do usuário logado
    """

    if current_user.is_authenticated:
        g.empresa_id = getattr(current_user, "id_empresa", None)
    else:
        g.empresa_id = None


# =========================================================
# PEGAR EMPRESA ATUAL (PADRÃO GLOBAL)
# =========================================================
def get_empresa_id():
    """
    Fonte única da empresa atual.
    """

    empresa_id = getattr(g, "empresa_id", None)

    if empresa_id is None:
        raise PermissionError(
            "Acesso negado: empresa não identificada no contexto."
        )

    return empresa_id


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


# =========================================================
# QUERY SEGURA (RECOMENDADO PARA NOVO CÓDIGO)
# =========================================================
def aplicar_filtro_empresa(sql: str, params=(), alias: str = ""):
    empresa_id = get_empresa_id()

    campo = f"{alias}.id_empresa" if alias else "id_empresa"

    sql = sql.replace(
        "/*empresa*/",
        f"{campo} = %s"
    )

    return sql, (*params, empresa_id)

# =========================================================
# QUERY SEGURA (LEGADO CONTROLADO)
# =========================================================
def query_empresa(cur, sql, params=(), alias=""):
    empresa_id = get_empresa_id()

    campo = f"{alias}.id_empresa" if alias else "id_empresa"

    if "WHERE" in sql.upper():
        sql += f" AND {campo} = %s"
    else:
        sql += f" WHERE {campo} = %s"

    cur.execute(sql, (*params, empresa_id))
    return cur.fetchall()

# =========================================================
# EXECUTOR SEGURO (OPCIONAL)
# =========================================================
def execute_secure(query, params=(), fetch=False):
    empresa_id = get_empresa_id()

    with get_conn() as conn:
        with conn.cursor() as cur:

            # suporte a dict params
            if isinstance(params, dict):
                params["empresa_id"] = empresa_id

            cur.execute(query, params)

            if fetch:
                return cur.fetchall()

            conn.commit()
            return None