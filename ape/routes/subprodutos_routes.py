from flask import Blueprint, redirect, url_for
from flask_login import login_required


subprodutos_bp = Blueprint("subprodutos", __name__)


@subprodutos_bp.route("/subprodutos")
@login_required
def listar_subprodutos():
    return redirect(url_for("estoque.estoque_painel"))
