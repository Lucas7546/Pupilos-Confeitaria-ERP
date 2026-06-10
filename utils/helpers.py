from flask_login import current_user
from PIL import Image
from modules.tenant_db import db_conn

def is_admin():
    return getattr(current_user, "nivel", None) == "admin"

def is_empresa():
    return bool(getattr(current_user, "id_empresa", None))

def _parse_float(valor: str, default: float = 0.0) -> float:
    try:
        if not valor:
            return default
        return float(str(valor).replace(",", ".").strip())
    except (ValueError, TypeError):
        return default

def validar_imagem_segura(arquivo):
    try:
        img = Image.open(arquivo)
        img.verify()

        arquivo.seek(0)

        # tentativa real de leitura (mais seguro)
        Image.open(arquivo).load()

        arquivo.seek(0)
        return True

    except Exception:
        return False
    


def query(sql, params=()):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()