from flask import Blueprint, redirect, url_for
from flask_login import login_required


equipe_bp = Blueprint("equipe", __name__)


@equipe_bp.route("/equipe")
@login_required
def equipe():
    return redirect(url_for("usuarios.usuarios"))
