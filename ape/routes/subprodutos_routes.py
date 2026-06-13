from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
from utils.helpers import _parse_float
from modules import estoque
from utils.logger import log_erro
from modules.tenant_db import db_conn
from ape.extensions import limiter
from modules.tenant import get_empresa_id

subprodutos_bp = Blueprint('subprodutos', __name__)


@subprodutos_bp.route('/historico-subproduto/<int:id_subproduto>')
@login_required
def historico_subproduto(id_subproduto):
    historico = estoque.buscar_historico_subproduto(id_subproduto)
    # Aqui você precisaria de um template 'historico_subproduto.html'
    # Por enquanto, para testar se funciona, podemos retornar o próprio histórico:
    return render_template('historico_subproduto.html', historico=historico, id_sub=id_subproduto)


@subprodutos_bp.route("/cadastrar-subproduto", methods=["POST"])
@login_required
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{g.id_empresa}") # Limite da empresa
def cadastrar_subproduto():
    nome    = request.form.get("nome", "").strip()
    unidade = request.form.get("unidade", "").strip()
    est_min = _parse_float(request.form.get("estoque_minimo", "0"))

    if not nome or not unidade:
        flash("Nome e Unidade são obrigatórios.", "warning")
    else:
        ok = estoque.cadastrar_subproduto_banco(current_user.id_empresa, nome, unidade, est_min)

        if ok: 
            registrar_log("CADASTRO", "SUBPRODUTO", f"Novo subproduto: {nome}", current_user.username)
            flash(f"Subproduto '{nome}' cadastrado!", "success")
        else:
            flash("Erro ao criar subproduto.", "danger")
    return redirect(url_for("insumos.render_cadastro"))

@subprodutos_bp.route("/excluir-subproduto/<int:id_subproduto>")
@login_required
@acesso_requerido("estoque")
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{g.id_empresa}") # Limite da empresa
def deletar_subproduto(id_subproduto):
    if estoque.excluir_subproduto_banco(current_user.id_empresa, id_subproduto):
        registrar_log("EXCLUIR", "SUBPRODUTO", f"ID {id_subproduto}", current_user.username)
        flash("Subproduto removido!", "success")
    return redirect(url_for("estoque.estoque_painel"))

@subprodutos_bp.route("/subprodutos/registrar-lote", methods=["POST"])
@login_required
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{g.id_empresa}") # Limite da empresa
def registrar_lote():
    nome_comercial   = request.form.get("nome", "").strip()
    preco_venda_raw  = request.form.get("preco", "").strip()
    id_subproduto_raw = request.form.get("id_subproduto")
    qtd_lote_raw     = request.form.get("quantidade", "").strip()

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
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
                    registrar_log("ALTERAR", "PRODUTOS", f"Preço '{nome_comercial}' → R$ {preco_venda:.2f}", current_user.username)
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
                    registrar_log("ESTOQUE", "SUBPRODUTOS", f"Lote {qtd} → Subproduto ID {id_sub}", current_user.username)
                    flash("Lote registrado!", "success")
                else:
                    flash("Dados insuficientes.", "warning")
    except Exception as e:
        log_erro(f"Erro ao registrar lote: {e}")
        flash(f"Erro: {e}", "danger")

    return redirect(url_for("estoque.estoque_painel"))



@subprodutos_bp.route('/ajustar-subproduto/<int:id_subproduto>', methods=['POST'])
@login_required
def ajustar_estoque_subproduto(id_subproduto):
    try:
        nova_qtd = request.form.get("quantidade")
        observacao = request.form.get("observacao", "Ajuste manual")
        
        if not nova_qtd:
            flash("Quantidade inválida.", "danger")
            return redirect(url_for("estoque.estoque_painel"))
            
        qtd = float(nova_qtd)
        # Certifique-se que g.id_empresa está disponível ou use get_empresa_id()
        id_empresa = get_empresa_id() 
        
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO movimentacao_estoque 
                    (id_empresa, id_subproduto, tipo_movimento, quantidade, observacao)
                    VALUES (%s, %s, 'ajuste', %s, %s)
                """, (id_empresa, id_subproduto, qtd, observacao))
        
        registrar_log("AJUSTE", "SUBPRODUTOS", f"ID {id_subproduto}: {qtd}", current_user.username)
        flash("Ajuste registrado!", "success")
    except Exception as e:
        log_erro(f"Erro ao ajustar: {e}")
        flash("Erro ao salvar ajuste.", "danger")
        
    return redirect(url_for("estoque.estoque_painel"))


