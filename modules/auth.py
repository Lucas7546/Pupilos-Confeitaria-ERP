from flask_login import UserMixin
from flask import session
from modules.usuarios import buscar_usuario, buscar_usuario_id
from werkzeug.security import check_password_hash


# =============================================================
# USER MODEL
# =============================================================
class User(UserMixin):
    def __init__(self, id_usuario: int, username: str, nivel: str):
        self.id = id_usuario
        self.username = username
        self.nivel = nivel


# =============================================================
# FLASK-LOGIN LOADER
# =============================================================
def load_user(user_id: str):
    """
    Reconstrói usuário sem bater no banco em toda request.

    Estratégia:
    1. Usa session (rápido)
    2. Fallback no banco (caso session expire)
    """

    if not user_id:
        return None

    username = session.get("username")
    nivel = session.get("nivel")

    # =========================================================
    # FAST PATH (SEM BANCO)
    # =========================================================
    if username and nivel:
        return User(int(user_id), username, nivel)

    # =========================================================
    # FALLBACK (BANCO)
    # =========================================================
    try:
        usuario = buscar_usuario_id(int(user_id))
        if not usuario:
            return None

        # Caso retorno seja dict
        if hasattr(usuario, "keys"):
            if not usuario.get("ativo"):
                return None

            return User(
                usuario["id_usuario"],
                usuario["username"],
                usuario["nivel"]
            )

        # Caso retorno seja tuple
        id_u, username_db, _senha, nivel_db, ativo = usuario[:5]

        if not ativo:
            return None

        return User(id_u, username_db, nivel_db)

    except Exception:
        return None


# =============================================================
# VALIDAR LOGIN
# =============================================================
def validar_login(username: str, senha: str):
    """
    Valida credenciais no login.
    Retorna User ou None.
    """

    usuario = buscar_usuario(username)

    if not usuario:
        return None

    try:
        id_user, username_db, senha_db, nivel_db, ativo = usuario[:5]
    except Exception:
        return None

    if int(ativo) == 0:
        return None

    if not check_password_hash(senha_db, senha):
        return None

    return User(id_user, username_db, nivel_db)