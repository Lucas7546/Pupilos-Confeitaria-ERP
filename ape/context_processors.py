from flask_login import current_user
from modules.tenant_db import get_conn

def inject_empresa():
    if not current_user.is_authenticated or not hasattr(current_user, 'id_empresa'):
        return {"EMPRESA": "Confeitaria ERP"}

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Busca a empresa pelo ID do usuário logado
                cur.execute("SELECT nome FROM empresas WHERE id_empresa = %s", (current_user.id_empresa,))
                result = cur.fetchone()
                
                if result:
                    return {
                        "EMPRESA": result[0], # O primeiro campo da query (nome)
                        "ID_EMPRESA": current_user.id_empresa
                    }
    except Exception as e:
        print(f"Erro ao buscar empresa: {e}")

    return {"EMPRESA": "Nome Padrão"}