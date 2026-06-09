from flask import g, request, has_request_context, session
from flask_login import current_user
from modules.tenant_db import get_conn as tenant_conn

EXCLUIR_PATHS = ["/static", "/favicon.ico", "/login"]

def set_empresa_context():
    # Ignora caminhos irrelevantes
    if any(request.path.startswith(p) for p in EXCLUIR_PATHS):
        return

    # Tenta pegar da sessão primeiro, que é mais estável que o current_user
    id_empresa = session.get("id_empresa")
    
    # Fallback para o current_user se a sessão estiver vazia mas logado
    if not id_empresa and current_user and current_user.is_authenticated:
        id_empresa = getattr(current_user, "id_empresa", None)

    g.id_empresa = id_empresa

    if not g.id_empresa:
        # Isso vai te mostrar exatamente em qual rota o sistema "esqueceu" a empresa
        print(f"DEBUG: Tenant não definido para a rota: {request.path}")

# =========================================================
# GET PADRÃO
# =========================================================
def get_empresa_id():
    if has_request_context() and hasattr(g, 'id_empresa') and g.id_empresa:
        return g.id_empresa
    
    if has_request_context() and session.get("id_empresa"):
        return session.get("id_empresa")
    
    # 3. Tenta o current_user (se estiver logado)
    if current_user and current_user.is_authenticated and hasattr(current_user, 'id_empresa'):
        return current_user.id_empresa

    # Se nada funcionar, vamos logar o estado real para debug
    raise Exception("Tenant não definido (Falha crítica de contexto)")

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
    # Pega o ID de forma mais robusta
    id_empresa = session.get("id_empresa") or getattr(current_user, "id_empresa", None)
    
    if not id_empresa:
        raise Exception("Tenant não definido - Falha no contexto de sessão")

    with tenant_conn() as conn:
        with conn.cursor() as cur:
            # Se params for tupla, convertemos para lista para adicionar o ID
            if isinstance(params, (list, tuple)):
                params = list(params)
                params.append(id_empresa)
                cur.execute(query, params)
            elif isinstance(params, dict):
                params["id_empresa"] = id_empresa
                cur.execute(query, params)
            else:
                cur.execute(query + " WHERE id_empresa = %s", (id_empresa,))

def get_empresa_id_safe():
    return getattr(g, "id_empresa", None)