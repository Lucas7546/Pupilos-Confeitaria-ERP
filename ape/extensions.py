from flask_login import LoginManager, UserMixin, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from modules.usuarios import buscar_usuario_id 


class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["id_usuario"])
        self.username = user_data["username"]
        self.nivel = user_data["nivel"]
        self.ativo = user_data["ativo"]
        self.id_empresa = user_data["id_empresa"]

login_manager = LoginManager()
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = buscar_usuario_id(int(user_id))
        if user_data and user_data['ativo']:
            return User(user_data)
    except (ValueError, TypeError):
        pass # Se não for um ID válido, simplesmente não carrega o usuário
    return None

# =============================================================
# RATE LIMIT
# =============================================================
def rate_limit_key():
    # Proteção: Verifica se o user está logado e se tem ID
    if current_user and current_user.is_authenticated:
        return f"u:{current_user.id}"
    return get_remote_address()

limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
# =============================================================
# INIT APP
# =============================================================
def init_extensions(app):
    login_manager.init_app(app)
    limiter.init_app(app)

@limiter.request_filter
def handle_ratelimit_error(e):
    # Isso será disparado quando alguém for bloqueado
    print(f"Bloqueado pelo Limiter: {e.description}")