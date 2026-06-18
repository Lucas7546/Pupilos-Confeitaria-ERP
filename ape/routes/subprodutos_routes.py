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
    try:
        id_empresa = get_empresa_id()

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT nome
                    FROM subprodutos
                    WHERE id_subproduto = %s
                      AND id_empresa = %s
                """, (id_subproduto, id_empresa))

                row = cur.fetchone()

                if not row:
                    flash("Subproduto não encontrado.", "warning")
                    return redirect(url_for("estoque.estoque_painel"))

                nome_subproduto = row[0]

        historico = estoque.buscar_historico_subproduto(id_subproduto) or []

        registrar_log(
            "CONSULTA",
            "HISTORICO_SUBPRODUTO",
            f"ID {id_subproduto}",
            current_user.username
        )

        return render_template(
            "historico_subproduto.html",
            historico=historico,
            id_sub=id_subproduto,
            nome_subproduto=nome_subproduto
        )

    except Exception as e:
        log_erro(f"Erro histórico subproduto: {e}")
        flash("Erro ao carregar histórico.", "danger")
        return redirect(url_for("estoque.estoque_painel"))

@subprodutos_bp.route("/cadastrar-subproduto", methods=["POST"])
@login_required
@limiter.limit("15 per minute")
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{g.id_empresa}")
def cadastrar_subproduto():

    try:
        id_empresa = get_empresa_id()

        nome = request.form.get("nome", "").strip()
        unidade = request.form.get("unidade", "").strip()
        est_min = _parse_float(request.form.get("estoque_minimo", "0"))

        # =========================
        # VALIDAÇÕES BÁSICAS
        # =========================
        if not nome or not unidade:
            flash("Nome e Unidade são obrigatórios.", "warning")
            return redirect(url_for("insumos.render_cadastro"))

        if len(nome) > 120:
            flash("Nome muito longo.", "warning")
            return redirect(url_for("insumos.render_cadastro"))

        if est_min is None or est_min < 0:
            est_min = 0

        nome_norm = nome.lower()

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =========================
                # EVITA DUPLICIDADE POR EMPRESA
                # =========================
                cur.execute("""
                    SELECT 1
                    FROM subprodutos
                    WHERE LOWER(nome) = %s
                      AND id_empresa = %s
                """, (nome_norm, id_empresa))

                if cur.fetchone():
                    flash("Já existe um subproduto com esse nome.", "warning")
                    return redirect(url_for("insumos.render_cadastro"))

                # =========================
                # INSERT SEGURO
                # =========================
                cur.execute("""
                    INSERT INTO subprodutos
                    (id_empresa, nome, unidade_medida, estoque_minimo)
                    VALUES (%s, %s, %s, %s)
                """, (
                    id_empresa,
                    nome,
                    unidade,
                    est_min
                ))

        registrar_log(
            "CADASTRO",
            "SUBPRODUTO",
            f"{nome}",
            current_user.username
        )

        flash(f"Subproduto '{nome}' cadastrado!", "success")

    except Exception as e:
        log_erro(f"Erro ao cadastrar subproduto: {e}")
        flash("Erro ao criar subproduto.", "danger")

    return redirect(url_for("insumos.render_cadastro"))

@subprodutos_bp.route("/excluir-subproduto/<int:id_subproduto>")
@login_required
@acesso_requerido("estoque")
@limiter.limit("15 per minute")
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{g.id_empresa}")
def deletar_subproduto(id_subproduto):

    try:
        id_empresa = get_empresa_id()

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =========================
                # VALIDA EXISTÊNCIA + TENANT
                # =========================
                cur.execute("""
                    SELECT 1
                    FROM subprodutos
                    WHERE id_subproduto = %s
                      AND id_empresa = %s
                """, (id_subproduto, id_empresa))

                if not cur.fetchone():
                    flash("Subproduto não encontrado.", "warning")
                    return redirect(url_for("estoque.estoque_painel"))

                # =========================
                # VERIFICA USO EM RECEITAS
                # =========================
                cur.execute("""
                    SELECT 1
                    FROM receitas
                    WHERE id_subproduto = %s
                      AND id_empresa = %s
                    LIMIT 1
                """, (id_subproduto, id_empresa))

                if cur.fetchone():
                    flash("Subproduto está em uso e não pode ser excluído.", "danger")
                    return redirect(url_for("estoque.estoque_painel"))

                # =========================
                # DELETE SEGURO
                # =========================
                cur.execute("""
                    DELETE FROM subprodutos
                    WHERE id_subproduto = %s
                      AND id_empresa = %s
                """, (id_subproduto, id_empresa))

                if cur.rowcount == 0:
                    raise Exception("Falha ao excluir subproduto")

        registrar_log(
            "EXCLUIR",
            "SUBPRODUTO",
            f"ID {id_subproduto}",
            current_user.username
        )

        flash("Subproduto removido!", "success")

    except Exception as e:
        log_erro(f"Erro ao excluir subproduto: {e}")
        flash("Erro ao excluir subproduto.", "danger")

    return redirect(url_for("estoque.estoque_painel"))
@subprodutos_bp.route("/subprodutos/registrar-lote", methods=["POST"])
@login_required
@limiter.limit("15 per minute")
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{g.id_empresa}")
def registrar_lote():
    nome_comercial = request.form.get("nome", "").strip()
    preco_venda_raw = request.form.get("preco", "").strip()
    id_subproduto_raw = request.form.get("id_subproduto")
    qtd_lote_raw = request.form.get("quantidade", "").strip()

    try:
        id_empresa = get_empresa_id()

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =========================
                # ALTERAÇÃO DE PREÇO
                # =========================
                if nome_comercial and preco_venda_raw:
                    preco_venda = _parse_float(preco_venda_raw)

                    if preco_venda is None or preco_venda < 0:
                        flash("Preço inválido.", "danger")
                        return redirect(url_for("estoque.estoque_painel"))

                    cur.execute("""
                        UPDATE produtos
                        SET preco_venda = %s
                        WHERE nome = %s
                          AND id_empresa = %s
                    """, (
                        preco_venda,
                        nome_comercial,
                        id_empresa
                    ))

                    if cur.rowcount == 0:
                        flash("Produto não encontrado.", "warning")
                        return redirect(url_for("estoque.estoque_painel"))

                    registrar_log(
                        "ALTERAR",
                        "PRODUTOS",
                        f"Preço '{nome_comercial}' → R$ {preco_venda:.2f}",
                        current_user.username
                    )

                    flash(f"Preço de '{nome_comercial}' atualizado!", "success")

                # =========================
                # ENTRADA DE LOTE
                # =========================
                elif id_subproduto_raw and qtd_lote_raw:
                    id_sub = int(id_subproduto_raw)
                    qtd = _parse_float(qtd_lote_raw)

                    if qtd is None or qtd <= 0:
                        flash("Quantidade inválida.", "danger")
                        return redirect(url_for("estoque.estoque_painel"))

                    # valida subproduto
                    cur.execute("""
                        SELECT nome
                        FROM subprodutos
                        WHERE id_subproduto = %s
                          AND id_empresa = %s
                    """, (id_sub, id_empresa))

                    sub = cur.fetchone()

                    if not sub:
                        flash("Subproduto não encontrado.", "warning")
                        return redirect(url_for("estoque.estoque_painel"))

                    nome_subproduto = sub[0]

                    # atualiza estoque
                    cur.execute("""
                        UPDATE subprodutos
                        SET quantidade_atual = COALESCE(quantidade_atual, 0) + %s
                        WHERE id_subproduto = %s
                          AND id_empresa = %s
                    """, (
                        qtd,
                        id_sub,
                        id_empresa
                    ))

                    # registra histórico
                    cur.execute("""
                        INSERT INTO movimentacao_estoque
                        (id_empresa, id_subproduto, tipo_movimento, quantidade, observacao)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_empresa,
                        id_sub,
                        "entrada_lote",
                        qtd,
                        "Entrada manual de lote"
                    ))

                    registrar_log(
                        "ESTOQUE",
                        "SUBPRODUTOS",
                        f"Lote {qtd} → {nome_subproduto}",
                        current_user.username
                    )

                    flash("Lote registrado com sucesso!", "success")

                else:
                    flash("Dados insuficientes.", "warning")

    except Exception as e:
        log_erro(f"Erro ao registrar lote: {e}")
        flash(f"Erro ao registrar lote: {e}", "danger")

    return redirect(url_for("estoque.estoque_painel"))

@subprodutos_bp.route('/ajustar-subproduto/<int:id_subproduto>', methods=['POST'])
@login_required
def ajustar_estoque_subproduto(id_subproduto):

    try:
        nova_qtd = request.form.get("quantidade", "").strip()
        observacao = request.form.get("observacao", "Ajuste manual")

        qtd = _parse_float(nova_qtd)

        if qtd is None:
            flash("Quantidade inválida.", "danger")
            return redirect(url_for("estoque.estoque_painel"))

        if abs(qtd) > 1_000_000:
            flash("Quantidade fora do limite permitido.", "danger")
            return redirect(url_for("estoque.estoque_painel"))

        id_empresa = get_empresa_id()

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =========================
                # VALIDA SUBPRODUTO
                # =========================
                cur.execute("""
                    SELECT 1
                    FROM subprodutos
                    WHERE id_subproduto = %s
                      AND id_empresa = %s
                """, (id_subproduto, id_empresa))

                if not cur.fetchone():
                    flash("Subproduto não encontrado.", "danger")
                    return redirect(url_for("estoque.estoque_painel"))

                # =========================
                # INSERT MOVIMENTO SEGURO
                # =========================
                cur.execute("""
                    INSERT INTO movimentacao_estoque 
                    (id_empresa, id_subproduto, tipo_movimento, quantidade, observacao)
                    VALUES (%s, %s, 'ajuste', %s, %s)
                """, (
                    id_empresa,
                    id_subproduto,
                    qtd,
                    observacao
                ))

        registrar_log(
            "AJUSTE",
            "SUBPRODUTOS",
            f"ID {id_subproduto}: {qtd}",
            current_user.username
        )

        flash("Ajuste registrado com segurança!", "success")

    except Exception as e:
        log_erro(f"Erro ao ajustar subproduto: {e}")
        flash("Erro ao salvar ajuste.", "danger")

    return redirect(url_for("estoque.estoque_painel"))


@subprodutos_bp.route("/subprodutos")
@login_required
def listar():
    try:
        subprodutos = estoque.listar_subprodutos() or []

        registrar_log(
            "CONSULTA",
            "SUBPRODUTOS",
            f"{len(subprodutos)} itens carregados",
            current_user.username
        )

        return render_template(
            "listar_subprodutos.html",
            subprodutos=subprodutos
        )

    except Exception as e:
        log_erro(f"Erro ao listar subprodutos: {e}")
        flash("Erro ao carregar subprodutos.", "danger")
        return redirect(url_for("estoque.estoque_painel"))