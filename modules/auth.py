from flask_login import UserMixin
from modules import usuarios
 
 
class User(UserMixin):
    def __init__(self, id_usuario: int, username: str, nivel: str):
        self.id = id_usuario
        self.username = username
        self.nivel = nivel
 
 
def load_user(user_id: str) -> "User | None":
    """
    Chamado pelo Flask-Login a cada request autenticado.
 
    PROBLEMA ORIGINAL: buscava o usuário no banco a cada request,
    consumindo uma conexão do pool por chamada — com 10 users ativos
    simultâneos já esgotava o pool.
 
    SOLUÇÃO: busca no banco só na primeira vez (login). Nas demais,
    reconstrói o objeto User com os dados já salvos na session do Flask,
    que vive em memória/cookie e não precisa de banco.
 
    Segurança: se o usuário for desativado, ele só perde acesso no
    próximo login — aceitável para este caso de uso. Se precisar de
    revogação imediata, troque para sempre buscar no banco e aumente
    o maxconn do pool.
    """
    if not user_id:
        return None
 
    # Importa aqui para evitar circular import
    from flask import session
 
    username = session.get("username")
    nivel    = session.get("nivel")
 
    # Se a session tem os dados, reconstrói sem bater no banco
    if username and nivel:
        return User(int(user_id), username, nivel)
 
    # Fallback: session perdida (ex: restart do servidor) — busca no banco
    usuario = usuarios.buscar_usuario_id(int(user_id))
    if not usuario:
        return None
 
    # Suporta DictCursor (dict) e cursor padrão (tupla)
    if hasattr(usuario, "keys"):
        if not usuario.get("ativo"):
            return None
        return User(usuario["id_usuario"], usuario["username"], usuario["nivel"])
 
    id_u, username_db, _senha, nivel_db, ativo = usuario[:5]
    if not ativo:
        return None
    return User(id_u, username_db, nivel_db)