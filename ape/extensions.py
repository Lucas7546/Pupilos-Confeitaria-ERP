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


def rate_limit_key():
    """
    Rate limit por usuário autenticado, fallback para IP.
    """
    # Proteção: só tente acessar o id se o user_loader estiver configurado
    try:
        if current_user and current_user.is_authenticated:
            return str(current_user.id)
    except:
        pass
    return get_remote_address()

limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["200 per day", "50 per hour"]
)
# =============================================================
# INIT APP
# =============================================================
def init_extensions(app):
    login_manager.init_app(app)
    limiter.init_app(app)

# =============================================================
# RATE LIMIT
# =============================================================

def get_rate_limit_key():
    try:
        if current_user.is_authenticated:
            return f"user:{current_user.id}"
    except Exception:
        pass

    return get_remote_address()

