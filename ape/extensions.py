from flask_login import LoginManager, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# =============================================================
# EXTENSIONS (SEM APP AINDA)
# =============================================================

login_manager = LoginManager()
login_manager.login_view = "auth.login"



def rate_limit_key():
    """
    Rate limit por usuário autenticado, fallback para IP.
    """
    if current_user and getattr(current_user, "is_authenticated", False):
        return str(current_user.id)

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
