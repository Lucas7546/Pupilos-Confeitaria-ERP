from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from utils.logger import log_erro
from modules import usuarios
from modules.permissoes import acesso_requerido

equipe_bp = Blueprint('equipe', __name__)

# A função _requer_nivel pode ficar aqui se for usada apenas neste módulo
def _requer_nivel(*niveis) -> bool:

    nivel = getattr(current_user, "nivel", None)

    if not nivel:
        nivel = session.get("nivel")

    if nivel not in niveis:

        flash(
            "Você não possui permissão para acessar esta página.",
            "danger"
        )

        return True

    return False

@equipe_bp.route("/equipe")
@login_required
@acesso_requerido("usuarios")
def gerenciar_equipe():

    try:

        return render_template(
            "equipe.html",
            equipe=usuarios.listar_usuarios() or []
        )

    except Exception as e:

        log_erro(f"Erro gerenciar_equipe: {e}")

        flash("Erro ao carregar equipe.", "danger")

        return redirect(url_for("main.dashboard"))
