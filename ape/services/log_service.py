from modules.tenant_db import db_conn
from flask_login import current_user

def registrar_log(acao, modulo, detalhe="", usuario=None):
    try:
        if not usuario:
            usuario = getattr(current_user, "username", "Sistema")

        id_empresa = getattr(current_user, "id_empresa", 0) or 0

        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO logs (id_empresa, usuario, acao, modulo, detalhe)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id_empresa, usuario, acao, modulo, detalhe))

    except Exception as e:
        print(f"Erro no log: {e}")