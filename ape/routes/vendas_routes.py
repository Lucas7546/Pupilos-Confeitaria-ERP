from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
import uuid
from utils.logger import log_erro
from ape.extensions import limiter
import os
from modules import importador_ia as ia
from modules import produtos, vendas, receitas
from modules.db import get_conn

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
                f"{resultado['quantidade_vendas']} vendas importadas"
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

@vendas_bp.route("/vendas")
@login_required
@acesso_requerido("vendas")
@limiter.limit("60 per minute")
def pagina_vendas():

    try:

        return render_template(
            "vendas.html",
            produtos=produtos.buscar_produto_por_nome("") or [],
            historico_vendas=vendas.listar_vendas_recentes() or [],
        )

    except Exception as e:

        log_erro(f"Erro na página de vendas: {e}")

        flash(
            "Erro ao carregar vendas.",
            "danger"
        )

        return redirect(
            url_for("main.dashboard")
        )

@vendas_bp.route("/vender", methods=["POST"])
@login_required
@acesso_requerido("vendas")
@limiter.limit("60 per minute")
def vender():

    id_p_raw = request.form.get("id_produto", "")
    qtd_raw = request.form.get("quantidade", "")

    if not id_p_raw.isdigit() or not qtd_raw.isdigit():
        flash("Dados inválidos.", "danger")
        return redirect(url_for("vendas.pagina_vendas"))

    id_p = int(id_p_raw)
    qtd = int(qtd_raw)

    if qtd <= 0:
        flash("Quantidade deve ser maior que zero.", "warning")
        return redirect(url_for("vendas.pagina_vendas"))

    prods = produtos.buscar_produto_por_nome("") or []

    produto = next(
        (p for p in prods if p[0] == id_p),
        None
    )

    if not produto:
        flash("Produto não encontrado.", "danger")
        return redirect(url_for("vendas.pagina_vendas"))

    if not receitas.validar_estoque_suficiente(id_p, qtd):
        flash("Estoque insuficiente.", "danger")
        return redirect(url_for("vendas.pagina_vendas"))

    valor_total = float(produto[2]) * qtd

    usuario_atual = getattr(
        current_user,
        "username",
        "Sistema"
    )

    if vendas.registrar_venda(
        id_produto=id_p,
        quantidade=qtd,
        valor_total=valor_total,
        usuario=usuario_atual
    ):

        registrar_log(
            "VENDA",
            "VENDAS",
            f"Prod {id_p} | Qtd {qtd} | R$ {valor_total:.2f}"
        )

        flash(
            "Venda registrada!",
            "success"
        )

    else:

        flash(
            "Erro ao registrar venda.",
            "danger"
        )

    return redirect(
        url_for("vendas.pagina_vendas")
    )

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


@vendas_bp.route("/confirmar-importacao", methods=["POST"])
@login_required
@acesso_requerido("vendas")
@limiter.limit("10 per minute")
def confirmar_importacao():

    try:
        total = request.form.get("total_itens", "0")

        try:
            total = int(total)
        except:
            total = 0

        if total <= 0:
            flash("Nenhum item para importar.", "warning")
            return redirect(url_for("vendas.central_importacoes"))

        salvos = 0

        with get_conn() as conn:
            with conn.cursor() as cur:

                for i in range(min(total, 100)):

                    nome = request.form.get(f"nome_{i}", "").strip()
                    preco = request.form.get(f"preco_{i}", "").strip()

                    try:
                        preco = float(preco)
                    except:
                        preco = 0

                    if not nome:
                        continue

                    # =========================
                    # INSERE OU ATUALIZA PRODUTO
                    # =========================
                    cur.execute("""
                        SELECT id_produto
                        FROM produtos
                        WHERE LOWER(nome) = LOWER(%s)
                        LIMIT 1
                    """, (nome,))

                    existe = cur.fetchone()

                    if existe:
                        id_produto = existe[0]
                        cur.execute("""
                            UPDATE produtos
                            SET preco_venda = %s
                            WHERE id_produto = %s
                        """, (preco, id_produto))

                    else:
                        cur.execute("""
                            INSERT INTO produtos (nome, preco_venda, categoria)
                            VALUES (%s, %s, 'Importado')
                            RETURNING id_produto
                        """, (nome, preco))

                        id_produto = cur.fetchone()[0]

                    salvos += 1

            conn.commit()

        registrar_log(
            "IMPORTACAO",
            "VENDAS",
            f"{salvos} produtos importados",
            current_user.username
        )

        flash(f"{salvos} itens importados com sucesso!", "success")

        return redirect(url_for("vendas.pagina_vendas"))

    except Exception as e:
        log_erro(f"Erro importação vendas: {e}")
        flash("Erro ao importar dados.", "danger")
        return redirect(url_for("vendas.central_importacoes"))
    


