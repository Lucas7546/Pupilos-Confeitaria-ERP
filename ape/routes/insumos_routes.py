from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
from utils.logger import log_erro
from utils.helpers import _parse_float
from modules import produtos, estoque

insumos_bp = Blueprint('insumos', __name__)

@insumos_bp.route("/cadastro")
@login_required
def render_cadastro():
    try:
        return render_template(
            "cadastro.html",
            produtos=produtos.listar_todos() or [],
            materias=estoque.listar_materia_prima() or [],
            subprodutos=estoque.listar_subprodutos() or [],
        )
    except Exception as e:
        log_erro(f"Erro ao renderizar cadastro: {e}")
        flash("Erro ao carregar a central de cadastros.", "danger")
        return redirect(url_for("main.dashboard"))

@insumos_bp.route("/cadastrar-mp", methods=["POST"])
@login_required
def cadastrar_mp():
    nome    = request.form.get("nome", "").strip()
    unidade = request.form.get("unidade", "").strip()
    preco   = _parse_float(request.form.get("preco", ""))
    est_at  = _parse_float(request.form.get("estoque_atual", "0"))
    est_min = _parse_float(request.form.get("estoque_minimo", "0"))

    if not nome or not unidade or preco <= 0:
        flash("Nome, Unidade e Preço são obrigatórios.", "warning")
        return redirect(url_for("insumos.render_cadastro"))

    if estoque.cadastrar_materia(nome, unidade, preco, est_at, est_min):
        registrar_log("CADASTRO", "MATERIA_PRIMA", f"{nome} | R$ {preco}")
        flash(f"Insumo '{nome}' salvo!", "success")
    else:
        flash("Erro ao salvar insumo.", "danger")

    return redirect(url_for("insumos.render_cadastro"))

@insumos_bp.route("/editar-materia-prima/<int:id_mp>", methods=["POST"])
@login_required
def processar_edicao_mp(id_mp):
    nome     = request.form.get("nome", "").strip()
    unidade  = request.form.get("unidade", "").strip()
    preco    = _parse_float(request.form.get("preco_custo", "0"))
    qtd      = _parse_float(request.form.get("quantidade", "0"))

    if not nome or not unidade:
        flash("Nome e Unidade são obrigatórios.", "warning")
        return redirect(url_for("estoque.estoque_painel"))

    if preco < 0 or qtd < 0:
        flash("Valores numéricos inválidos.", "danger")
        return redirect(url_for("estoque.estoque_painel"))

    if estoque.atualizar_materia_prima(id_mp, nome, preco, unidade, qtd):
        registrar_log("ALTERAR", "MATERIA_PRIMA", f"ID {id_mp} → {nome} | Qtd {qtd}")
        flash("Matéria-prima atualizada!", "success")
    else:
        flash("Erro ao atualizar matéria-prima.", "danger")

    return redirect(url_for("estoque.estoque_painel"))

@insumos_bp.route("/excluir-mp/<int:id_mp>", methods=["POST"])
@login_required
@acesso_requerido("estoque")
def deletar_mp(id_mp):
    if estoque.excluir_materia_prima(id_mp):
        registrar_log("DELETAR", "MATERIA_PRIMA", f"ID {id_mp} removido por '{current_user.username}'")
        flash("Matéria-prima excluída!", "success")
    else:
        flash("Não foi possível remover o insumo.", "warning")
    return redirect(url_for("estoque.estoque_painel"))

@insumos_bp.route('/registrar-compra', methods=['POST'])
@login_required
def rota_registrar_compra():
    try:
        id_mp = request.form.get('id_materia_prima')
        qtd = request.form.get('quantidade')
        valor = request.form.get('preco_total')

        sucesso = estoque.registrar_compra_estoque(
            int(id_mp),
            float(qtd),
            float(valor)
        )

        if sucesso:
            return jsonify({"status": "success"}), 200

        return jsonify({"status": "error"}), 400

    except Exception as e:
        log_erro(f"Erro registrar compra: {e}")
        return jsonify({"status": "error", "message": "erro interno"}), 500