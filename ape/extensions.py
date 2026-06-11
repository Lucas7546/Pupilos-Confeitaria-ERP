from flask_login import LoginManager, UserMixin, current_user, AnonymousUserMixin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from modules.usuarios import buscar_usuario_global_cached
from flask import session
from modules.db import release_conn, get_conn_raw, get_pool
from psycopg2.extras import DictCursor



# =============================================================
# HACK: AnonymousUser customizado
# =============================================================
class AnonymousUser(AnonymousUserMixin):
    def __init__(self):
        super().__init__()
        self.id_empresa = None 
        self.id = None
# =============================================================
# USER MODEL
# =============================================================

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["id_usuario"])
        self.id_usuario = user_data["id_usuario"]
        self.username = user_data["username"]
        self.nivel = user_data["nivel"]
        self.ativo = user_data["ativo"]
        self.id_empresa = user_data["id_empresa"]

        self.is_superadmin = user_data.get(
            "is_superadmin",
            False
        )

# =============================================================
# LOGIN MANAGER
# =============================================================
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    conn = get_pool().getconn()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT id_usuario, username, nivel, id_empresa, ativo, is_superadmin
                FROM usuarios
                WHERE id_usuario = %s
            """, (user_id,))

            user_data = cur.fetchone()

        if not user_data or not user_data.get("ativo"):
            return None

        return User(user_data)

    finally:
        get_pool().putconn(conn)
# =============================================================
# RATE LIMIT KEY (AGORA COM EMPRESA)
# =============================================================
def rate_limit_key():
    try:
        # Verifica se o current_user existe e se ele tem o id_empresa
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            # Se for um usuário real e logado
            if getattr(current_user, 'id_empresa', None):
                return f"u:{current_user.id_empresa}:{current_user.id}"
    except Exception:
        pass
    
    # Fallback para visitantes
    return get_remote_address()

limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)


# =============================================================
# INIT EXTENSIONS
# =============================================================
def init_extensions(app):
    login_manager.init_app(app)
    limiter.init_app(app)
    login_manager.anonymous_user = AnonymousUser


# =============================================================
# ERROR HANDLER RATE LIMIT
# =============================================================
@limiter.request_filter
def handle_ratelimit_error(*args, **kwargs):
    # aqui NÃO é erro, é filtro
    return False