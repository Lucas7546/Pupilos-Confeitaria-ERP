from functools import wraps
from flask import abort
from flask_login import current_user
from modules import usuarios

# Hierarquia de acesso da Pupilos Confeitaria
PERMISSOES = {
    "admin": ["usuarios", "estoque", "vendas", "financeiro", "cadastro", "auditoria"],
    "gerente": ["estoque", "vendas", "financeiro", "cadastro", "auditoria"],
    "funcionario": ["estoque", "vendas"],
    "bloqueado": []
}

def usuario_logado():
    """Recupera os dados completos do usuário logado no banco Postgres."""
    if not current_user.is_authenticated:
        return None
    
    # O current_user.id geralmente vem do Flask-Login
    return usuarios.buscar_usuario_id(current_user.id)

def pode_acessar(modulo):
    """Verifica se o nível do usuário permite acesso ao módulo solicitado."""
    usuario = usuario_logado()

    if not usuario:
        return False

    # No Postgres, garantimos que o nível seja tratado em minúsculo para bater com o dicionário
    # usuario[2] ou usuario[3] dependendo da ordem do seu SELECT em usuarios.py
    # Com base no nosso script de criação: 0:id, 1:username, 2:senha, 3:nivel
    try:
        nivel = str(usuario[3]).lower()
    except (IndexError, AttributeError):
        return False

    permissoes = PERMISSOES.get(nivel, [])

    return modulo in permissoes

def acesso_requerido(modulo):
    """Decorator para proteger as rotas do Flask."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Se o usuário não tiver permissão, o Flask interrompe com erro 403 (Proibido)
            if not pode_acessar(modulo):
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator