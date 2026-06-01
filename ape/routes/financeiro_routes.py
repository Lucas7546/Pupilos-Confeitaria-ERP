from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
from modules import financeiro 
from utils.helpers import _parse_float

financeiro_bp = Blueprint('financeiro', __name__)

@financeiro_bp.route("/financeiro")
@login_required
@acesso_requerido("financeiro")
def pagina_financeiro():
    dados = financeiro.financeiro_operacional()
    return render_template("financeiro.html", **dados)

@financeiro_bp.route("/relatorio-financeiro")
@login_required
@acesso_requerido("financeiro")
def relatorio_financeiro():
    dados = financeiro.relatorio_fiscal()
    return render_template("relatorio_financeiro.html", **dados)

@financeiro_bp.route("/despesas", methods=["GET", "POST"])
@login_required
@acesso_requerido("financeiro")
def despesas():
    if request.method == "POST":
        descricao = request.form.get("descricao", "").strip()
        valor_raw = request.form.get("valor", "0")
        valor = _parse_float(valor_raw)

        if not descricao or valor <= 0:
            flash("Dados inválidos.", "danger")
        elif financeiro.registrar_despesa(descricao, valor):
            registrar_log("CADASTRAR", "DESPESAS", f"'{descricao}' R$ {valor:.2f}")
            flash("Despesa cadastrada!", "success")
        else:
            flash("Erro ao salvar no banco.", "danger")
        return redirect(url_for("financeiro.despesas"))

    return render_template("despesa.html", despesas=financeiro.listar_despesas())


@financeiro_bp.route("/fluxo-caixa")
@login_required
@acesso_requerido("financeiro")
def fluxo_caixa():

    dados = financeiro.get_fluxo_caixa()

    movs = dados["movimentacoes"]

    entradas = sum(m["valor"] for m in movs if m["tipo"] == "ENTRADA")
    saidas = sum(m["valor"] for m in movs if m["tipo"] == "SAIDA")

    return render_template(
        "fluxo_caixa.html",
        movimentacoes=movs,
        total_entradas=entradas,
        total_saidas=saidas,
        saldo_caixa=entradas - saidas
    )