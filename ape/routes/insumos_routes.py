from flask import Blueprint, render_template
from flask_login import login_required

from modules import estoque, produtos


insumos_bp = Blueprint("insumos", __name__)


@insumos_bp.route("/insumos")
@login_required
def render_cadastro():
    return render_template(
        "cadastro.html",
        materias=estoque.listar_materia_prima() or [],
        produtos=produtos.listar_todos() or [],
        subprodutos=estoque.listar_subprodutos() or [],
    )
