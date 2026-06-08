from modules.usuarios import buscar_usuario
from werkzeug.security import check_password_hash
from ape.extensions import User


def validar_login(username: str, senha: str):
    usuario = buscar_usuario(username)

    if not usuario:
        return None

    if not usuario.get("ativo"):
        return None

    senha_hash_banco = usuario.get("senha")

    if not senha_hash_banco:
        return None

    if check_password_hash(senha_hash_banco, senha):
        return User(usuario)

    return None