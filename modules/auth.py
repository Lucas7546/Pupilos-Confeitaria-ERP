from flask_login import UserMixin
from flask import session
from modules.usuarios import buscar_usuario, buscar_usuario_id
from werkzeug.security import check_password_hash


# =============================================================
# USER MODEL
# =============================================================
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['id_usuario'])
        self.username = user_data['username']
        self.nivel = user_data['nivel']
        self.ativo = user_data['ativo']
        # MULTIEMPRESA
        self.id_empresa = user_data('id_empresa')


# =============================================================
# FLASK-LOGIN LOADER
# =============================================================
def load_user(user_id: str):

    if not user_id:
        return None

    username = session.get("username")
    nivel = session.get("nivel")
    id_empresa = session.get("id_empresa")

    # =========================================================
    # FAST PATH (SEM BANCO)
    # =========================================================
    if username and nivel and id_empresa:

        return User(
            int(user_id),
            username,
            nivel,
            id_empresa
        )

    # =========================================================
    # FALLBACK (BANCO)
    # =========================================================
    try:

        usuario = buscar_usuario_id(int(user_id))

        if not usuario:
            return None

        if hasattr(usuario, "keys"):

            if not usuario.get("ativo"):
                return None

            return User(
                usuario["id_usuario"],
                usuario["username"],
                usuario["nivel"],
                usuario["id_empresa"]
            )

        return None

    except Exception:
        return None


# =============================================================
# VALIDAR LOGIN
# =============================================================
def validar_login(username: str, senha: str):

    usuario = buscar_usuario(username)

    if not usuario:
        return None

    try:

        id_user = usuario["id_usuario"]
        username_db = usuario["username"]
        senha_db = usuario["senha"]
        nivel_db = usuario["nivel"]
        ativo = usuario["ativo"]
        id_empresa = usuario["id_empresa"]

    except Exception:
        return None

    if int(ativo) == 0:
        return None

    if not check_password_hash(senha_db, senha):
        return None

    return User(
        id_user,
        username_db,
        nivel_db,
        id_empresa
    )