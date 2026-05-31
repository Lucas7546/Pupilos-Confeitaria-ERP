from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
from utils.logger import log_erro
from ape.extensions import limiter
import os
from modules import importador_ia as ia
from modules import produtos, vendas, receitas

vendas_bp = Blueprint('vendas', __name__)

@vendas_bp.route("/importacoes")
@login_required
@acesso_requerido("vendas")
def central_importacoes():
    return render_template("central_importacoes.html")

@vendas_bp.route("/importar-ifood", methods=["POST"])
@login_required
@acesso_requerido("vendas")
@limiter.limit("5 per minute")
def importar_ifood():
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        flash("Nenhum arquivo selecionado.", "warning")
        return redirect(url_for("vendas.central_importacoes"))

    resultado = ia.processar_relatorio_delivery(arquivo)

    if resultado["sucesso"]:
        registrar_log("IMPORTAR_IFOOD","VENDAS", f"{resultado['quantidade_vendas']} vendas importadas")
        flash(f"Importação concluída! {resultado['quantidade_vendas']} vendas processadas.", "success")
    else:
        flash(f"Erro na importação: {resultado['erro']}", "danger")

    return redirect(url_for("vendas.central_importacoes"))


@vendas_bp.route("/vendas")
@login_required
def pagina_vendas():
    try:
        return render_template(
            "vendas.html",
            produtos=produtos.buscar_produto_por_nome("") or [],
            historico_vendas=vendas.listar_vendas_recentes() or [],
        )
    except Exception as e:
        log_erro(f"Erro na página de vendas: {e}")
        flash("Erro ao carregar vendas.", "danger")
        return redirect(url_for("main.dashboard"))

@vendas_bp.route("/vender", methods=["POST"])
@login_required
@limiter.limit("60 per minute")
def vender():
    id_p_raw = request.form.get("id_produto", "")
    qtd_raw  = request.form.get("quantidade", "")

    if not id_p_raw.isdigit() or not qtd_raw.isdigit():
        flash("Dados inválidos.", "danger")
        return redirect(url_for("vendas.pagina_vendas"))

    id_p, qtd = int(id_p_raw), int(qtd_raw)
    if qtd <= 0:
        flash("Quantidade deve ser maior que zero.", "warning")
        return redirect(url_for("vendas.pagina_vendas"))

    # Lógica de validação
    prods = produtos.buscar_produto_por_nome("") or []
    produto = next((p for p in prods if p[0] == id_p), None)
    
    if not produto:
        flash("Produto não encontrado.", "danger")
        return redirect(url_for("vendas.pagina_vendas"))

    if not receitas.validar_estoque_suficiente(id_p, qtd):
        flash("Estoque insuficiente.", "danger")
        return redirect(url_for("vendas.pagina_vendas"))

    valor_total = float(produto[2]) * qtd
    usuario_atual = getattr(current_user, "username", "Sistema")
    
    if vendas.registrar_venda(id_produto=id_p, quantidade=qtd, valor_total=valor_total, usuario=usuario_atual):
        registrar_log("VENDA", "VENDAS", f"Prod {id_p} | Qtd {qtd} | R$ {valor_total:.2f}")
        flash("Venda registrada!", "success")
    else:
        flash("Erro ao registrar venda.", "danger")

    return redirect(url_for("vendas.pagina_vendas"))

@vendas_bp.route("/deletar-venda/<int:id_venda>")
@login_required
@acesso_requerido("vendas")
def deletar_venda(id_venda):
    if vendas.excluir_venda(id_venda):
        registrar_log("ESTORNO", "VENDAS", f"Venda {id_venda} cancelada por '{current_user.username}'")
        flash("Venda estornada e estoque devolvido!", "success")
    else:
        flash("Não foi possível estornar a venda.", "warning")
    return redirect(url_for("vendas.pagina_vendas"))