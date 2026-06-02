from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from modules import produtos, estoque
from utils.helpers import _parse_float
from ape.services.log_service import registrar_log


vinculos_bp = Blueprint('vinculos', __name__)

@vinculos_bp.route("/vincular-receita", methods=["POST"])
@login_required
def vincular_receita():
    id_p = request.form.get("id_produto")
    id_m = request.form.get("id_materia_prima")
    qtd  = _parse_float(request.form.get("quantidade", "0"))

    if not id_p or not id_m or qtd <= 0:
        flash("Selecione produto, insumo e informe quantidade > 0.", "warning")
        return redirect(url_for("insumos.render_cadastro"))

    if produtos.vincular_insumo(id_p, id_m, qtd):
        registrar_log("CADASTRO", "FICHA_TECNICA", f"MP {id_m} → Prod {id_p} | Qtd {qtd}")
        flash("Ingrediente vinculado!", "success")
    return redirect(url_for("insumos.render_cadastro"))


@vinculos_bp.route("/vincular-subproduto-produto", methods=["POST"])
@login_required
def vincular_subproduto_produto():
    id_p   = request.form.get("id_produto")
    id_sub = request.form.get("id_subproduto")
    qtd    = _parse_float(request.form.get("quantidade", "0"))

    if not id_p or not id_sub or qtd <= 0:
        flash("Dados incompletos.", "warning")
        return redirect(url_for("insumos.render_cadastro"))

    if produtos.vincular_subproduto_ao_produto(id_p, id_sub, qtd):
        registrar_log("VINCULAR","FICHA_TECNICA",f"Subproduto {id_sub} -> Produto {id_p} | Qtd {qtd}")

        flash("Subproduto vinculado ao produto!", "success")
    return redirect(url_for("insumos.render_cadastro"))

@vinculos_bp.route("/vincular-receita-subproduto", methods=["POST"])
@login_required
def vincular_receita_subproduto():
    id_sub = request.form.get("id_subproduto")
    id_m   = request.form.get("id_materia_prima")
    qtd    = _parse_float(request.form.get("quantidade", "0"))
 
    if not id_sub or not id_m or qtd <= 0:
        flash("Dados incompletos.", "warning")
        return redirect(url_for("insumos.render_cadastro"))
 
    if estoque.vincular_insumo_subproduto(id_sub, id_m, qtd):
        registrar_log( "VINCULAR", "SUBPRODUTO",f"MP {id_m} -> Subproduto {id_sub} | Qtd {qtd}")
        flash("Ingrediente vinculado ao subproduto!", "success")
    else:
        flash("Erro ao vincular.", "danger")
 
    return redirect(url_for("insumos.render_cadastro"))

