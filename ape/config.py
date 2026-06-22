import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    
    if not SECRET_KEY:
        raise ValueError("A variável de ambiente SECRET_KEY não foi definida!")

    JSON_SORT_KEYS = False

    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True  # True em produção HTTPS
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_DOMAIN = None