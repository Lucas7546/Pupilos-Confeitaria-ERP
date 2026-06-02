from flask import g
from flask_login import current_user

def init_tenant(app):

    @app.before_request
    def set_empresa():

        if current_user.is_authenticated:
            g.empresa_id = getattr(current_user, "id_empresa", None)
        else:
            g.empresa_id = None

