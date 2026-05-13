from functools import wraps
from flask import abort
from modules import usuarios


PERMISSOES = {
    "admin": ["usuarios", "estoque", "vendas", "financeiro", "cadastro", "auditoria"],
    "gerente": ["estoque", "vendas", "financeiro", "cadastro", "auditoria"],
    "funcionario": ["estoque", "vendas"],
    "bloqueado": []
}


def usuario_logado():
    from flask_login import current_user

    if not current_user.is_authenticated:
        return None

    return usuarios.buscar_usuario(current_user.id)


def pode_acessar(modulo):

    usuario = usuario_logado()

    if not usuario:
        return False

    nivel = usuario[3]

    permissoes = PERMISSOES.get(nivel, [])

    return modulo in permissoes


def acesso_requerido(modulo):

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):

            if not pode_acessar(modulo):
                abort(403)

            return f(*args, **kwargs)

        return wrapper

    return decorator