from flask_login import UserMixin
from modules import usuarios


class User(UserMixin):
    def __init__(self, id_usuario: int, username: str, nivel: str):
        self.id = id_usuario
        self.username = username
        self.nivel = nivel


def load_user(user_id: str) -> "User | None":
    """
    Chamado pelo Flask-Login em cada request autenticado.
    Busca o usuário diretamente no banco — não depende da session,
    o que evita estados inconsistentes após reset de cookie.

    Bug corrigido: o módulo usuarios expõe `buscar_usuario_id`,
    não `buscar_usuario_por_id`. Nome alinhado aqui.
    """
    if not user_id:
        return None

    usuario = usuarios.buscar_usuario_id(int(user_id))
    if not usuario:
        return None

    # Suporta tanto DictCursor (dict) quanto cursor padrão (tupla)
    if hasattr(usuario, "keys"):
        if not usuario.get("ativo"):
            return None
        return User(usuario["id_usuario"], usuario["username"], usuario["nivel"])

    id_u, username, _senha, nivel, ativo = usuario[:5]
    if not ativo:
        return None
    return User(id_u, username, nivel)