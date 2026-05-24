from functools import wraps
from flask import abort
from flask_login import current_user
from modules import usuarios
from flask import redirect, url_for, flash # adicione os imports caso não existam no topo

# Hierarquia de acesso da Pupilos Confeitaria
# O nome aqui deve bater exatamente com o que está no Banco de Dados
PERMISSOES = {
    "admin": ["usuarios", "estoque", "vendas", "financeiro", "cadastro", "auditoria", "produtos"],
    "socios": ["estoque", "vendas", "financeiro", "cadastro", "auditoria", "produtos"],
    "dono": ["estoque", "vendas", "financeiro", "cadastro", "auditoria", "produtos"],
    "financeiro":["financeiro", "vendas", "cadastro" ],
    "colaborador": ["estoque", "vendas"],
    "ti": ["usuarios","auditoria"],
    "bloqueado": []
}

def usuario_logado():
    """Recupera os dados completos do usuário logado no banco Postgres."""
    if not current_user.is_authenticated:
        return None
    
    # Busca os dados no banco usando o ID (username) salvo na sessão
    return usuarios.buscar_usuario_id(current_user.id)

def pode_acessar(modulo):
    usuario = usuario_logado()
    if not usuario:
        return False

    # A MARRETA: Se você logar como admin, você manda em tudo, ponto final.
    if str(usuario[3]).lower() == 'admin':
        nivel = 'admin'
    else:
        try:
            nivel = str(usuario[3]).lower()
        except:
            nivel = 'bloqueado'

    permissoes = PERMISSOES.get(nivel, [])
    return modulo in permissoes

def acesso_requerido(modulo):
    """Decorator para proteger as rotas do Flask com redirecionamento amigável."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not pode_acessar(modulo):
                print(f"Acesso NEGADO para o módulo: {modulo}")
                flash("Você não tem permissão para acessar este módulo.", "danger")
                return redirect(url_for("dashboard")) # Redireciona para a página principal
            return f(*args, **kwargs)
        return wrapper
    return decorator








