from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
import uuid
from modules.planos import plano_requerido
from utils.logger import log_erro
from ape.extensions import limiter
import os
from modules import importador_ia as ia
from modules import produtos, vendas, receitas
from modules.tenant_db import db_conn

vendas_bp = Blueprint('vendas', __name__)



@vendas_bp.route("/vendas")
@login_required
@acesso_requerido("vendas")
@limiter.limit("15 per minute")
@limiter.limit("100 per hour", key_func=lambda: f"empresa:{getattr(g, 'id_empresa', 'global')}")
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
@limiter.limit("30 per minute")
@limiter.limit("100 per hour", key_func=lambda: f"empresa:{getattr(g, 'id_empresa', 'global')}")
def vender():
    nome_produto = request.form.get("nome_produto", "").strip() # Pega o nome
    qtd_raw = request.form.get("quantidade", "")

    # Validação simples
    if not nome_produto or not qtd_raw.isdigit():
        flash("Dados inválidos.", "danger")
        return redirect(url_for("vendas.pagina_vendas"))

    qtd = int(qtd_raw)
    
    # Busca o produto pelo NOME (usando a função que você já tem no 'produtos')
    prods = produtos.buscar_produto_por_nome(nome_produto) or []
    
    # Se 'buscar_produto_por_nome' retorna uma lista, pegamos o primeiro item
    produto = prods[0] if prods else None

    if not produto:
        flash("Produto não encontrado.", "danger")
        return redirect(url_for("vendas.pagina_vendas"))

    id_p = produto[0] # Pega o ID que está no banco a partir do produto achado

    if not receitas.validar_estoque_suficiente(id_p, qtd):
        flash("Estoque insuficiente.", "danger")
        return redirect(url_for("vendas.pagina_vendas"))

    valor_total = float(produto[2]) * qtd # Supondo que o preço é o índice 2
    usuario_atual = getattr(current_user, "username", "Sistema")

    if vendas.registrar_venda(id_produto=id_p, quantidade=qtd, valor_total=valor_total, usuario=usuario_atual):
        registrar_log("VENDA", "VENDAS", f"{nome_produto} | Qtd {qtd} | R$ {valor_total:.2f}", current_user.username)
        flash("Venda registrada!", "success")
    else:
        flash("Erro ao registrar venda.", "danger")

    return redirect(url_for("vendas.pagina_vendas"))

@vendas_bp.route("/importacoes")
@login_required
@acesso_requerido("vendas")
@plano_requerido("premium")
@limiter.limit("10 per minute")
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{getattr(g, 'id_empresa', 'global')}")
def central_importacoes():
    return render_template("central_importacoes.html")

@vendas_bp.route("/importar-ifood", methods=["POST"])
@login_required
@acesso_requerido("vendas")
@plano_requerido("premium")
@limiter.limit("10 per minute")
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{getattr(g, 'id_empresa', 'global')}")
def importar_ifood():

    arquivo = request.files.get("arquivo")

    if not arquivo or not arquivo.filename:
        flash(
            "Nenhum arquivo selecionado.",
            "warning"
        )
        return redirect(
            url_for("vendas.central_importacoes")
        )

    try:

        resultado = ia.processar_relatorio_delivery(
            arquivo
        )

        if resultado["sucesso"]:

            registrar_log(
                "IMPORTACAO",
                "VENDAS",
                f"{resultado['quantidade_vendas']} vendas importadas", current_user.username
            )

            flash(
                f"{resultado['quantidade_vendas']} vendas importadas com sucesso.",
                "success"
            )

        else:

            flash(
                resultado.get(
                    "erro",
                    "Erro ao importar."
                ),
                "danger"
            )

    except Exception as e:

        log_erro(
            f"Erro rota importação: {e}"
        )

        flash(
            "Erro ao processar importação.",
            "danger"
        )

    return redirect(
        url_for("vendas.central_importacoes")
    )

@vendas_bp.route("/deletar-venda/<int:id_venda>")
@login_required
@acesso_requerido("vendas")
@limiter.limit("15 per minute")
@limiter.limit("100 per hour", key_func=lambda: f"empresa:{getattr(g, 'id_empresa', 'global')}")
def deletar_venda(id_venda):
    if vendas.excluir_venda(id_venda):
        registrar_log("ESTORNO", "VENDAS", f"Venda {id_venda} cancelada por '{current_user.username}'", current_user.username)
        flash("Venda estornada e estoque devolvido!", "success")
    else:
        flash("Não foi possível estornar a venda.", "warning")
    return redirect(url_for("vendas.pagina_vendas"))




@vendas_bp.route("/importacao-preview", methods=["POST"])
@login_required
@acesso_requerido("vendas")
@plano_requerido("premium")
def importacao_preview():

    arquivo = request.files.get("arquivo")

    if not arquivo:
        return {"sucesso": False, "erro": "Arquivo não enviado"}

    try:
        preview = ia.processar_relatorio_delivery_preview(arquivo)
        return preview

    except Exception as e:
        log_erro(f"Erro preview importação: {e}")
        return {"sucesso": False, "erro": str(e)}
    

@vendas_bp.route("/importacao-confirmar", methods=["POST"])
@login_required
@acesso_requerido("vendas")
@plano_requerido("premium")
def importacao_confirmar():

    try:
        vendas_json = request.json.get("vendas", [])

        resultado = ia.processar_relatorio_delivery_commit(vendas_json)

        if resultado["sucesso"]:
            registrar_log(
                "IMPORTACAO",
                "VENDAS",
                f"{resultado['processadas']} vendas importadas", current_user.username
            )

        return resultado

    except Exception as e:
        log_erro(f"Erro confirmação importação: {e}")
        return {"sucesso": False, "erro": str(e)}