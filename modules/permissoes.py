from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from modules import usuarios
from utils.logger import log_info, log_erro

# Hierarquia de acesso da Pupilos Confeitaria
PERMISSOES = {
    "admin": ["usuarios", "estoque", "vendas", "financeiro", "cadastro", "auditoria", "produtos"],
    "socios": ["estoque", "vendas", "financeiro", "cadastro", "auditoria", "produtos"],
    "dono": ["estoque", "vendas", "financeiro", "cadastro", "auditoria", "produtos"],
    "financeiro": ["financeiro", "vendas", "cadastro"],
    "colaborador": ["estoque", "vendas"],
    "ti": ["usuarios", "auditoria"],
    "bloqueado": []
}

def usuario_logado():
    """Recupera os dados do usuário logado via banco."""
    if not current_user.is_authenticated:
        return None
    return usuarios.buscar_usuario_id(current_user.id)

def pode_acessar(modulo):
    usuario = usuario_logado()
    if not usuario:
        return False

    # Acesso seguro ao nível (assumindo que o retorno seja um dicionário ou objeto acessível)
    # Se você estiver usando DictCursor, o nome da coluna é o ideal
    nivel = str(usuario.get('nivel', 'bloqueado')).lower()

    if nivel == 'admin':
        return True

    permissoes = PERMISSOES.get(nivel, [])
    return modulo in permissoes

def acesso_requerido(modulo):
    """Decorator para proteger as rotas do Flask."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not pode_acessar(modulo):
                user_info = current_user.id if current_user.is_authenticated else "Anonimo"
                log_erro(f"Acesso NEGADO ao módulo '{modulo}' por usuário: {user_info}")
                
                flash("Você não tem permissão para acessar este módulo.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator








