from flask import Blueprint, request, redirect, flash, url_for
from modules.empresas import criar_empresa

empresas_bp = Blueprint("empresas", __name__)

@empresas_bp.route("/criar-empresa", methods=["POST"])
def criar_empresa_route():

    nome = request.form.get("nome")
    plano = request.form.get("plano", "basic")

    if not nome:
        flash("Nome obrigatório", "danger")
        return redirect(url_for("main.dashboard"))

    id_empresa = criar_empresa(nome, plano)

    flash(f"Empresa criada com ID {id_empresa}", "success")

    return redirect(url_for("main.dashboard"))