from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required
from modules.permissoes import acesso_requerido
from modules import usuarios

equipe_bp = Blueprint('equipe', __name__)

# A função _requer_nivel pode ficar aqui se for usada apenas neste módulo
def _requer_nivel(*niveis):
    if session.get("nivel") not in niveis:
        flash("Acesso negado!", "danger")
        return True
    return False

@equipe_bp.route("/equipe")
@login_required
def gerenciar_equipe():
    if _requer_nivel("admin", "socios"):
        return redirect(url_for("main.dashboard")))
    try:
        return render_template("equipe.html", equipe=usuarios.listar_usuarios() or [])
    except Exception as e:
        flash("Erro ao carregar equipe.", "danger")
        return redirect(url_for("main.dashboard"))
