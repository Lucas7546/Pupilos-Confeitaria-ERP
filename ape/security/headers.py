def aplicar_headers_seguranca(response):

    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; " # 'unsafe-inline' ainda é necessário se você usa styles dentro de tags <style>
        "script-src 'self' 'unsafe-inline'; " # 'unsafe-inline' ainda é necessário enquanto seus scripts estiverem no HTML
        "font-src 'self';"
    )