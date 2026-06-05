from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
from utils.helpers import _parse_float
from modules import estoque
from utils.logger import log_erro
from modules.db import get_conn
from ape.extensions import limiter

subprodutos_bp = Blueprint('subprodutos', __name__)

@subprodutos_bp.route("/cadastrar-subproduto", methods=["POST"])
@login_required
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def cadastrar_subproduto():
    nome    = request.form.get("nome", "").strip()
    unidade = request.form.get("unidade", "").strip()
    est_min = _parse_float(request.form.get("estoque_minimo", "0"))

    if not nome or not unidade:
        flash("Nome e Unidade são obrigatórios.", "warning")
    elif estoque.cadastrar_subproduto_banco(nome, unidade, est_min):
        registrar_log("CADASTRO", "SUBPRODUTO", f"Novo subproduto: {nome}")
        flash(f"Subproduto '{nome}' cadastrado!", "success")
    return redirect(url_for("insumos.render_cadastro"))

@subprodutos_bp.route("/excluir-subproduto/<int:id_subproduto>")
@login_required
@acesso_requerido("estoque")
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def deletar_subproduto(id_subproduto):
    if estoque.excluir_subproduto_banco(id_subproduto):
        registrar_log("EXCLUIR", "SUBPRODUTO", f"ID {id_subproduto}")
        flash("Subproduto removido!", "success")
    return redirect(url_for("estoque.estoque_painel"))

@subprodutos_bp.route("/subprodutos/registrar-lote", methods=["POST"])
@login_required
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def registrar_lote():
    nome_comercial   = request.form.get("nome", "").strip()
    preco_venda_raw  = request.form.get("preco", "").strip()
    id_subproduto_raw = request.form.get("id_subproduto")
    qtd_lote_raw     = request.form.get("quantidade", "").strip()

    try:
        with get_conn() as con:
            with con.cursor() as cur:
                # Lógica de Atualização de Preço
                if nome_comercial and preco_venda_raw:
                    preco_venda = _parse_float(preco_venda_raw)
                    if preco_venda < 0:
                        flash("Preço inválido.", "danger")
                        return redirect(url_for("estoque.estoque_painel"))
                    cur.execute(
                        "UPDATE produtos SET preco_venda = %s WHERE nome = %s",
                        (preco_venda, nome_comercial),
                    )
                    con.commit()
                    registrar_log("ALTERAR", "PRODUTOS", f"Preço '{nome_comercial}' → R$ {preco_venda:.2f}")
                    flash(f"Preço de '{nome_comercial}' atualizado!", "success")

                # Lógica de Entrada de Lote (Subprodutos)
                elif id_subproduto_raw and qtd_lote_raw:
                    id_sub = int(id_subproduto_raw)
                    qtd = _parse_float(qtd_lote_raw)
                    if qtd < 0:
                        flash("Quantidade inválida.", "danger")
                        return redirect(url_for("estoque.estoque_painel"))
                    cur.execute(
                        "UPDATE subprodutos SET quantidade_atual = COALESCE(quantidade_atual,0) + %s WHERE id_subproduto = %s",
                        (qtd, id_sub),
                    )
                    con.commit()
                    registrar_log("ESTOQUE", "SUBPRODUTOS", f"Lote {qtd} → Subproduto ID {id_sub}")
                    flash("Lote registrado!", "success")
                else:
                    flash("Dados insuficientes.", "warning")
    except Exception as e:
        log_erro(f"Erro ao registrar lote: {e}")
        flash(f"Erro: {e}", "danger")

    return redirect(url_for("estoque.estoque_painel"))