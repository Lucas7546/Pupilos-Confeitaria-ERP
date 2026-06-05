from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
from ape.extensions import limiter
from modules import financeiro as financeiro_service
from utils.helpers import _parse_float

financeiro_bp = Blueprint(
    "financeiro",
    __name__,
    template_folder="templates"
)

# =========================
# PAINEL FINANCEIRO
# =========================
@financeiro_bp.route("/financeiro", methods=["GET"])
@login_required
@acesso_requerido("financeiro")
def pagina_financeiro():
    dados = financeiro_service.financeiro_operacional()
    return render_template("financeiro.html", **dados)


# =========================
# RELATÓRIO FISCAL
# =========================
@financeiro_bp.route("/relatorio-financeiro", methods=["GET"])
@login_required
@acesso_requerido("financeiro")
def relatorio_financeiro():
    dados = financeiro_service.relatorio_fiscal()
    return render_template("relatorio_financeiro.html", **dados)


# =========================
# DESPESAS FIXAS
# =========================
@financeiro_bp.route("/despesas", methods=["GET", "POST"])
@login_required
@acesso_requerido("financeiro")
@limiter.limit("10 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def despesas():

    if request.method == "POST":

        descricao = request.form.get("descricao", "").strip()
        valor = _parse_float(request.form.get("valor", "0"))

        if not descricao or valor <= 0:
            flash("Dados inválidos.", "danger")
            return redirect(url_for("financeiro.despesas"))

        if financeiro_service.registrar_despesa(descricao, valor):
            registrar_log(
                "CADASTRAR",
                "DESPESAS",
                f"{descricao} R$ {valor:.2f}"
            )
            flash("Despesa cadastrada com sucesso!", "success")
        else:
            flash("Erro ao salvar no banco.", "danger")

        return redirect(url_for("financeiro.despesas"))

    despesas = financeiro_service.listar_despesas()
    return render_template("despesa.html", despesas=despesas)


# =========================
# FLUXO DE CAIXA
# =========================
@financeiro_bp.route("/fluxo-caixa", methods=["GET"])
@login_required
@acesso_requerido("financeiro")
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def fluxo_caixa():

    dados = financeiro_service.get_fluxo_caixa() or {}
    movs = dados.get("movimentacoes", []) or []

    entradas = sum(m.get("valor", 0) for m in movs if m.get("tipo") == "ENTRADA")
    saidas = sum(m.get("valor", 0) for m in movs if m.get("tipo") == "SAIDA")

    return render_template(
        "fluxo_caixa.html",
        movimentacoes=movs,
        total_entradas=entradas,
        total_saidas=saidas,
        saldo_caixa=entradas - saidas
    )