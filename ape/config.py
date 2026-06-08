import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-me")

    JSON_SORT_KEYS = False

    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True  # True em produção HTTPS
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_DOMAIN = None