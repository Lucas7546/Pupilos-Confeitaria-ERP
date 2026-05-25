from flask_login import UserMixin
from modules import usuarios


class User(UserMixin):
    def __init__(self, id_usuario, username, nivel):
        self.id = id_usuario
        self.username = username
        self.nivel = nivel


def load_user(user_id):
    usuario = usuarios.buscar_usuario_por_id(user_id)

    if not usuario:
        return None

    id_user, username_db, senha_db, nivel_db, ativo = usuario[:5]

    return User(id_user, username_db, nivel_db)