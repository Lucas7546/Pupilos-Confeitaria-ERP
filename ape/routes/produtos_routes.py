from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
from utils.logger import log_erro
from utils.helpers import _parse_float
from modules.db import get_conn
from modules import produtos, estoque
from psycopg2.extras import RealDictCursor
from ape.extensions import limiter

produtos_bp = Blueprint('produtos', __name__)

@produtos_bp.route("/cadastrar-produto", methods=["POST"])
@login_required
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def cadastrar_produto_final():
    nome      = request.form.get("nome", "").strip()
    preco     = _parse_float(request.form.get("preco", ""))
    categoria = request.form.get("categoria", "").strip()

    if not nome or preco <= 0:
        flash("Nome e Preço são obrigatórios.", "warning")
        return redirect(url_for("insumos.render_cadastro"))

    if produtos.cadastrar_produto(nome, preco, categoria):
        registrar_log("CADASTRO", "PRODUTO", f"{nome} | R$ {preco}")
        flash(f"Produto '{nome}' cadastrado!", "success")
    else:
        flash("Erro ao salvar produto.", "danger")
    return redirect(url_for("insumos.render_cadastro"))

@produtos_bp.route("/editar-produto/<int:id_produto>", methods=["POST"])
@login_required
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def atualizar_produto(id_produto):
    nome = request.form.get("nome", "").strip()
    preco = _parse_float(request.form.get("preco", "0").strip())

    if not nome:
        flash("O nome não pode ficar em branco.", "warning")
    elif preco < 0:
        flash("Preço inválido.", "danger")
    elif produtos.update_produto(id_produto, nome, preco):
        registrar_log("ALTERAR", "PRODUTOS", f"ID {id_produto} → {nome} | R$ {preco}")
        flash("Produto atualizado!", "success")
    else:
        flash("Erro ao atualizar produto.", "danger")
    return redirect(url_for("estoque.estoque_painel"))

@produtos_bp.route("/excluir-produto/<int:id_produto>", methods=["POST"])
@login_required
@acesso_requerido("estoque")
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def deletar_produto(id_produto):
    if produtos.excluir_produto(id_produto):
        registrar_log("DELETAR", "PRODUTOS", f"ID {id_produto} removido por '{current_user.username}'")
        flash("Produto excluído!", "success")
    else:
        flash("Não foi possível excluir o produto.", "warning")
    return redirect(url_for("estoque.estoque_painel"))

@produtos_bp.route("/precificacao")
@login_required
def precificacao():
    try:
        with get_conn() as con:
            with con.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.id_produto, p.nome, p.preco_venda,
                           COALESCE(SUM(r.quantidade_utilizada * mp.preco_unitario), 0) AS custo_producao
                    FROM produtos p
                    LEFT JOIN receitas r ON p.id_produto = r.id_produto
                    LEFT JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
                    WHERE p.ativo = 1 AND p.id_empresa = %s
                    GROUP BY p.id_produto, p.nome, p.preco_venda
                    ORDER BY p.nome ASC
                """)
                produtos_db = cur.fetchall()

        tabela = []
        for p in produtos_db:
            custo = float(p["custo_producao"])
            venda = float(p["preco_venda"])
            tabela.append({
                "id": p["id_produto"], "nome": p["nome"], "atual": venda,
                "custo": custo, "equilibrio": custo * 1.10,
                "sugerido": custo / 0.7 if custo > 0 else 0,
                "alerta": venda < (custo * 1.10) if custo > 0 else False,
            })
        return render_template("precificacao.html", tabela=tabela)
    except Exception as e:
        log_erro(f"Erro na precificação: {e}")
        flash(f"Erro ao carregar precificação: {e}", "danger")
        return redirect(url_for("estoque.estoque_painel"))
    

@produtos_bp.route("/ficha-tecnica/<int:id_produto>")
@login_required
def ficha_tecnica(id_produto):
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    "SELECT id_produto, nome, preco_venda FROM produtos WHERE id_produto = %s AND id_empresa = %s",
                    (id_produto, current_user.id_empresa),
                )
                produto = cur.fetchone()
                if not produto:
                    flash("Produto não encontrado.", "danger")
                    # Ajustado para o prefixo correto do estoque
                    return redirect(url_for("estoque.estoque_painel"))

                cur.execute("""
                    SELECT r.id_receita, 'materia_prima', mp.id_materia_prima, mp.nome,
                           r.quantidade_utilizada, mp.unidade_medida,
                           r.quantidade_utilizada * COALESCE(mp.preco_unitario, 0)
                    FROM receitas r
                    JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
                    WHERE r.id_produto = %s AND r.id_subproduto IS NULL
                    UNION ALL
                    SELECT r.id_receita, 'subproduto', sub.id_subproduto, sub.nome,
                           r.quantidade_utilizada, sub.unidade_medida,
                           r.quantidade_utilizada * COALESCE(sub.preco_custo_unidade, 0)
                    FROM receitas r
                    JOIN subprodutos sub ON r.id_subproduto = sub.id_subproduto
                    WHERE r.id_produto = %s AND r.id_subproduto IS NOT NULL
                """, (id_produto, id_produto))

                colunas = [d[0] for d in cur.description]
                itens = [dict(zip(colunas, row)) for row in cur.fetchall()]

        total_custo = sum(float(i.get("custo_subtotal") or i.get(colunas[6], 0)) for i in itens)
        preco_venda = float(produto[2] or 0)
        lucro = preco_venda - total_custo
        margem = (lucro / preco_venda * 100) if preco_venda > 0 else 0

        return render_template(
            "ficha_tecnica.html",
            produto=[produto[0], produto[1], preco_venda],
            itens=itens,
            total=round(total_custo, 2),
            lucro=round(lucro, 2),
            margem=round(margem, 2),
        )
    except Exception as e:
        log_erro(f"Erro na ficha técnica ID {id_produto}: {e}")
        flash(f"Erro ao processar ficha técnica: {e}", "danger")
        return redirect(url_for("estoque.estoque_painel"))

@produtos_bp.route("/ficha-tecnica/editar-item/<int:id_produto>", methods=["POST"])
@login_required
@limiter.limit("15 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def editar_item_ficha(id_produto):
    id_vinculo_raw = request.form.get("id_vinculo")
    qtd_raw = request.form.get("quantidade", "0").strip()

    if not id_vinculo_raw:
        flash("Vínculo inválido.", "warning")
        return redirect(url_for("produtos.ficha_tecnica", id_produto=id_produto))

    try:
        id_vinculo = int(id_vinculo_raw)
        nova_qtd = _parse_float(qtd_raw)
        if nova_qtd < 0:
            raise ValueError
    except ValueError:
        flash("Quantidade deve ser um número positivo.", "danger")
        return redirect(url_for("produtos.ficha_tecnica", id_produto=id_produto))

    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    "UPDATE receitas SET quantidade_utilizada = %s WHERE id_receita = %s AND id_produto = %s",
                    (nova_qtd, id_vinculo, id_produto),
                )
            con.commit()
        registrar_log("ALTERAR", "FICHA_TECNICA", f"Vínculo {id_vinculo} → {nova_qtd}")
        flash("Quantidade ajustada!", "success")
    except Exception as e:
        log_erro(f"Erro ao editar ficha técnica: {e}")
        flash(f"Erro ao salvar: {e}", "danger")

    return redirect(url_for("produtos.ficha_tecnica", id_produto=id_produto))
