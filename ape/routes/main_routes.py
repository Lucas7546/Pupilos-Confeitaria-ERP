from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from modules import vendas, produtos, estoque 
from utils.logger import log_erro 

main_bp = Blueprint('main', __name__)

@main_bp.route("/dashboard")
@login_required
@acesso_requerido("estoque")
def dashboard():
    valores_vazios = {"faturamento": 0, "total_vendas": 0, "lucro": 0}
    id_empresa = current_user.id_empresa
    try:
        resumo_diario  = vendas.obter_resumo_periodo(1, id_empresa)  or valores_vazios
        resumo_semanal = vendas.obter_resumo_periodo(7, id_empresa)  or valores_vazios
        resumo_mensal  = vendas.obter_resumo_periodo(30, id_empresa) or valores_vazios
        capacidade = produtos.calcular_capacidade_geral(id_empresa)

        if isinstance(resumo_semanal, dict):
            if 'valores_grafico' not in resumo_semanal:
                resumo_semanal['valores_grafico'] = [0, 0, 0, 0, 0, 0, 0]
            if 'dias_grafico' not in resumo_semanal:
                resumo_semanal['dias_grafico'] = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
        insumos = estoque.listar_materia_prima(id_empresa) or []
        criticos = [
            item for item in insumos
            if float(item[4] or 0) <= float(item[3] or 0)
        ]

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
            diario=valores_vazios, semana=valores_vazios, mes=valores_vazios,
            capacidade=[], criticos=[],
        )