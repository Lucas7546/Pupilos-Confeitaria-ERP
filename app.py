import os
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect
from flask import Flask, redirect, url_for
from ape.extensions import init_extensions
# Importando seus Blueprints organizados
from ape.routes.auth_routes import auth_bp
from ape.routes.estoque_routes import estoque_bp
from ape.routes.compras_routes import compras_bp
from ape.routes.empresas_routes import empresas_bp
from ape.routes.export_routes import export_bp
from ape.routes.main_routes import main_bp
from ape.routes.feedback_routes import feedback_bp
from ape.security.headers import aplicar_headers_seguranca
from ape.context_processors import inject_empresa
from ape.routes.vendas_routes import vendas_bp
from ape.routes.financeiro_routes import financeiro_bp
from ape.routes.usuarios_routes import usuarios_bp
from ape.routes.auditoria_routes import auditoria_bp
from ape.routes.api_routes import api_bp
from ape.routes.equipe_routes import equipe_bp
from ape.routes.insumos_routes import insumos_bp
from ape.routes.produtos_routes import produtos_bp
from ape.routes.vinculos_routes import vinculos_bp
from ape.routes.subprodutos_routes import subprodutos_bp



csrf = CSRFProtect()
def create_app():
    app = Flask(__name__, static_folder="static")

    app.config.from_object('ape.config.Config')

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    csrf.init_app(app)

    # EXTENSIONS PRIMEIRO
    init_extensions(app)

    
    
    @app.before_request
    def set_empresa_context():
        from flask import g, request, session, redirect, url_for, render_template
        from flask_login import current_user
        from modules.planos import get_plano_empresa
        from modules.tenant_db import db_conn
        from psycopg2.extras import DictCursor
        from modules.termos import TERMOS_VERSAO

        try:
            # 1. Static files (NUNCA bloquear)
            if request.path.startswith("/static/"):
                g.id_empresa = None
                return

            # 2. Usuário não logado
            if not current_user.is_authenticated:
                return

            # 3. Garantir empresa existe no usuário
            g.id_empresa = getattr(current_user, "id_empresa", None)

            if not g.id_empresa:
                return

            # 4. Rotas liberadas (CRÍTICO: inclui POST também)
            rotas_liberadas = {
                "auth.login",
                "auth.logout",
                "auditoria.aceitar_termos"
            }

            if request.endpoint in rotas_liberadas:
                return

            # 5. Cache plano (seguro)
            if session.get("id_empresa_cache") != g.id_empresa:
                session["plano"] = get_plano_empresa()
                session["id_empresa_cache"] = g.id_empresa

            # 6. Verificação de termos
            with db_conn() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("""
                        SELECT termos_aceitos, versao_termos
                        FROM empresas
                        WHERE id_empresa = %s
                    """, (g.id_empresa,))
                    res = cur.fetchone()

            # 7. Se não existir empresa → erro real
            if not res:
                return render_template("erro.html"), 500

            aceito = res.get("termos_aceitos") is True
            versao_bd = res.get("versao_termos") or "0"

            # DEBUG (remove depois)
            print(f"[TERMOS DEBUG] aceito={aceito} | bd={versao_bd} | code={TERMOS_VERSAO}")

            # 8. REGRA FINAL
            if (not aceito) or (versao_bd != TERMOS_VERSAO):
                return redirect(url_for("auditoria.aceitar_termos"))

        except Exception:
            import traceback
            print("[ERRO BEFORE REQUEST TERMOS]")
            print(traceback.format_exc())
            return render_template("erro.html"), 500

    @app.context_processor
    def inject_plano():
        from flask import session
        return dict(plano=session.get("plano", "starter"))            
    
    # Registro dos Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.context_processor(inject_empresa)
    app.register_blueprint(estoque_bp, url_prefix="/estoque")
    app.register_blueprint(compras_bp)
    app.register_blueprint(export_bp, url_prefix="/export")
    app.register_blueprint(vendas_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(financeiro_bp, url_prefix='/financeiro')
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(auditoria_bp)
    app.register_blueprint(equipe_bp)
    app.register_blueprint(insumos_bp)
    app.register_blueprint(produtos_bp, url_prefix='/produtos')
    app.register_blueprint(vinculos_bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(feedback_bp)
    app.register_blueprint(subprodutos_bp)
    
    app.after_request(aplicar_headers_seguranca)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app

# Inicialização para o Render/Servidor
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
