from flask import g
from flask_login import current_user

def init_tenant(app):

    @app.before_request
    def set_empresa():

        if (
            current_user.is_authenticated
            and hasattr(current_user, "id_empresa")
        ):
            g.empresa_id = current_user.id_empresa
        else:
            g.empresa_id = None

