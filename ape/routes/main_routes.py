from flask import Blueprint, render_template
from flask_login import login_required
from modules.permissoes import acesso_requerido
from modules import vendas, produtos, estoque
from utils.logger import log_erro
from modules.tenant import get_empresa_id

main_bp = Blueprint('main', __name__)


@main_bp.route("/dashboard")
@login_required
@acesso_requerido("estoque")
def dashboard():

    valores_vazios = {
        "faturamento": 0.0,
        "total_vendas": 0,
        "lucro": 0.0,
        "dias_grafico": [],
        "valores_grafico": [],
    }

    try:
        id_empresa = get_empresa_id()

        if not id_empresa:
            raise Exception("Empresa não definida no contexto")

        # =========================
        # RESUMOS (COM FALLBACK REAL)
        # =========================
        resumo_diario = vendas.obter_resumo_periodo(1)
        if not resumo_diario:
            resumo_diario = valores_vazios

        resumo_semanal = vendas.obter_resumo_periodo(7)
        if not resumo_semanal:
            resumo_semanal = valores_vazios

        resumo_mensal = vendas.obter_resumo_periodo(30)
        if not resumo_mensal:
            resumo_mensal = valores_vazios

        capacidade = produtos.calcular_capacidade_geral()

        # garante estrutura do gráfico
        resumo_semanal.setdefault("valores_grafico", [])
        resumo_semanal.setdefault("dias_grafico", [])

        # =========================
        # INSUMOS CRÍTICOS
        # =========================
        insumos = estoque.listar_materia_prima()

        criticos = []

        for item in insumos:
            try:
                saldo = float(item[4] or 0)
                minimo = float(item[3] or 0)

                if saldo <= minimo:
                    criticos.append(item)

            except Exception:
                continue

        return render_template(
            "dashboard.html",
            diario=resumo_diario,
            semana=resumo_semanal,
            mes=resumo_mensal,
            capacidade=capacidade,
            criticos=criticos,
        )

    except Exception as e:

        log_erro(f"Erro no dashboard: {e}")

        return render_template(
            "dashboard.html",
            diario=valores_vazios,
            semana=valores_vazios,
            mes=valores_vazios,
            capacidade=[],
            criticos=[],
        )