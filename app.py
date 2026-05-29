import os
from flask import Flask, redirect, url_for
from ape.extensions import init_extensions
# Importando seus Blueprints organizados
from ape.routes.auth_routes import auth_bp
from ape.routes.estoque_routes import estoque_bp
from ape.routes.compras_routes import compras_bp
from ape.routes.export_routes import export_bp
from ape.routes.main_routes import main_bp
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
from modules.db import init_db




def create_app():
    app = Flask(__name__)

    # Carrega configurações
    app.config.from_object('ape.config.Config')
    
    # Inicializa as extensões
    init_extensions(app)
    
    # Registro dos Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.context_processor(inject_empresa)
    app.register_blueprint(estoque_bp)
    app.register_blueprint(compras_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(vendas_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(financeiro_bp, url_prefix='/financeiro')
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(auditoria_bp)
    app.register_blueprint(equipe_bp)
    app.register_blueprint(insumos_bp)
    app.register_blueprint(produtos_bp)
    app.register_blueprint(vinculos_bp)
    app.register_blueprint(subprodutos_bp)
    
    app.after_request(aplicar_headers_seguranca)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    with app.app_context():
        init_db()

    return app

# Inicialização para o Render/Servidor
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
