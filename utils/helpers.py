from flask_login import current_user
from PIL import Image
from modules.tenant_db import db_conn
from modules.admin_db import admin_conn
from utils.logger import log_erro
from flask import request


def registrar_acesso(usuario, id_empresa=None, empresa_nome=None, tipo="LOGIN"):
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        user_agent = request.headers.get("User-Agent", "Desconhecido")

        with admin_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO acessos_sistema (
                        usuario,
                        id_empresa,
                        empresa_nome,
                        ip,
                        user_agent,
                        tipo_evento
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    usuario,
                    id_empresa,
                    empresa_nome,
                    ip,
                    user_agent,
                    tipo
                ))

    except Exception as e:
        log_erro(f"Erro registrar acesso: {e}")


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