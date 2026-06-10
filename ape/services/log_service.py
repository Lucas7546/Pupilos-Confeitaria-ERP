from modules.tenant_db import db_conn
from flask_login import current_user

def registrar_log(acao, modulo, detalhe="", usuario=None):
    try:
        # Se não enviaram o usuário manualmente, tenta pegar do contexto
        if not usuario and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            usuario = current_user.username
        elif not usuario:
            usuario = "Sistema"

        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO logs (id_empresa, usuario, acao, modulo, detalhe) VALUES (%s, %s, %s, %s, %s)",
                    (current_user.id_empresa, usuario, acao, modulo, detalhe),
                )
            conn.commit()
    except Exception as e:
        print(f"Erro no log: {e}")