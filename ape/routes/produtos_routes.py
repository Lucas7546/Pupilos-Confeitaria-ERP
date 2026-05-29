from flask import Blueprint, redirect, url_for
from flask_login import login_required


produtos_bp = Blueprint("produtos", __name__)


@produtos_bp.route("/produtos")
@login_required
def listar_produtos():
    return redirect(url_for("estoque.estoque_painel"))
