from functools import wraps

from flask import redirect, url_for, flash
from flask_login import current_user
from utils.logger import log_erro

# =========================================================
# HIERARQUIA DE PERMISSÕES
# =========================================================
PERMISSOES: dict[str, list[str]] = {
    "admin":       ["usuarios", "estoque", "vendas", "financeiro", "cadastro", "auditoria", "produtos"],
    "socios":      ["estoque", "vendas", "financeiro", "cadastro", "auditoria", "produtos"],
    "dono":        ["estoque", "vendas", "financeiro", "cadastro", "usuarios", "produtos"],
    "financeiro":  ["financeiro", "vendas", "cadastro"],
    "colaborador": ["estoque", "vendas"],
    "ti":          ["usuarios", "auditoria"],
    "bloqueado":   [],
}






def pode_acessar(modulo: str) -> bool:
    """
    Verifica permissão usando o nível já carregado no objeto User do Flask-Login.

    Bug corrigido: a versão anterior chamava `usuarios.buscar_usuario_id()`
    a cada request, gerando uma query de banco por rota protegida.
    O nível já existe em `current_user.nivel` após o login — usamos ele.
    """
    if not current_user.is_authenticated:
        return False

    nivel = str(getattr(current_user, "nivel", "bloqueado")).lower()

    if nivel == "admin":
        return True

    return modulo in PERMISSOES.get(nivel, [])



def acesso_requerido(modulo: str):
    """Decorator que protege rotas do Flask verificando o módulo permitido."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not pode_acessar(modulo):
                user_id = getattr(current_user, "id", "Anônimo")
                log_erro(f"Acesso NEGADO ao módulo '{modulo}' pelo usuário: {user_id}")
                flash("Você não tem permissão para acessar este módulo.", "danger")
                return redirect(url_for("main.dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator








