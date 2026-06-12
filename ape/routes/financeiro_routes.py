from flask import Blueprint, render_template, request, g, redirect, url_for, flash
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

    try:
        dados = financeiro_service.financeiro_operacional() or {}

        return render_template(
            "financeiro.html",
            **dados
        )

    except Exception as e:

        flash("Erro ao carregar painel financeiro.", "danger")

        return render_template(
            "financeiro.html",
            faturamento=0,
            despesas=0,
            lucro=0
        )


# =========================
# RELATÓRIO FISCAL
# =========================
@financeiro_bp.route("/relatorio-financeiro", methods=["GET"])
@login_required
@acesso_requerido("financeiro")
def relatorio_financeiro():

    try:
        dados = financeiro_service.relatorio_fiscal() or {}

        return render_template(
            "relatorio_financeiro.html",
            **dados
        )

    except Exception as e:

        flash("Erro ao gerar relatório financeiro.", "danger")

        return render_template(
            "relatorio_financeiro.html",
            vendas=[],
            total=0,
            impostos=0
        )


# =========================
# DESPESAS FIXAS
# =========================
@financeiro_bp.route("/despesas", methods=["GET", "POST"])
@login_required
@acesso_requerido("financeiro")
@limiter.limit("10 per minute")
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{g.id_empresa}")
def despesas():

    try:

        if request.method == "POST":

            descricao = request.form.get("descricao", "").strip()
            valor = _parse_float(request.form.get("valor", "0"))

            if not descricao or valor <= 0:
                flash("Dados inválidos.", "danger")
                return redirect(url_for("financeiro.despesas"))

            sucesso = financeiro_service.registrar_despesa(descricao, valor)

            if sucesso:

                registrar_log(
                    "CADASTRAR",
                    "DESPESAS",
                    f"{descricao} R$ {valor:.2f}"
                )

                flash("Despesa cadastrada com sucesso!", "success")

            else:
                flash("Erro ao salvar no banco.", "danger")

            return redirect(url_for("financeiro.despesas"))

        despesas = financeiro_service.listar_despesas() or []

        return render_template(
            "despesa.html",
            despesas=despesas
        )

    except Exception as e:

        flash("Erro no módulo de despesas.", "danger")

        return render_template(
            "despesa.html",
            despesas=[]
        )


# =========================
# FLUXO DE CAIXA
# =========================
@financeiro_bp.route("/fluxo-caixa", methods=["GET"])
@login_required
@acesso_requerido("financeiro")
@limiter.limit("15 per minute")
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{g.id_empresa}")
def fluxo_caixa():

    try:

        dados = financeiro_service.get_fluxo_caixa() or {}
        movs = dados.get("movimentacoes") or []

        entradas = sum(
            float(m.get("valor") or 0)
            for m in movs
            if m.get("tipo") == "ENTRADA"
        )

        saidas = sum(
            float(m.get("valor") or 0)
            for m in movs
            if m.get("tipo") == "SAIDA"
        )

        return render_template(
            "fluxo_caixa.html",
            movimentacoes=movs,
            total_entradas=entradas,
            total_saidas=saidas,
            saldo_caixa=entradas - saidas
        )

    except Exception as e:

        flash("Erro ao carregar fluxo de caixa.", "danger")

        return render_template(
            "fluxo_caixa.html",
            movimentacoes=[],
            total_entradas=0,
            total_saidas=0,
            saldo_caixa=0
        )