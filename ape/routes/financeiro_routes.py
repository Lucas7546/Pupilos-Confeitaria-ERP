from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from modules import financeiro


financeiro_bp = Blueprint("financeiro", __name__)


@financeiro_bp.route("/")
@login_required
def painel_financeiro():
    periodo = request.args.get("periodo", 30, type=int)
    dados = financeiro.calcular_financeiro_com_imposto(periodo)
    despesas = financeiro.listar_despesas()
    return render_template(
        "financeiro.html",
        financeiro=dados,
        despesas=despesas,
        periodo=periodo,
    )


@financeiro_bp.route("/despesa", methods=["POST"])
@login_required
def registrar_despesa():
    descricao = request.form.get("descricao", "").strip()
    valor = request.form.get("valor", "0").replace(",", ".")

    try:
        valor_float = float(valor)
    except ValueError:
        valor_float = 0

    if descricao and valor_float > 0 and financeiro.registrar_despesa(descricao, valor_float):
        flash("Despesa registrada.", "success")
    else:
        flash("Erro ao registrar despesa.", "danger")

    return redirect(url_for("financeiro.painel_financeiro"))
