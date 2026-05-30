from flask import ( Blueprint, request, jsonify, render_template, flash, redirect, url_for)
from flask_login import login_required, current_user
from ape.extensions import limiter
from ape.services import ai_client
from modules.db import get_conn
from modules import estoque, produtos
from utils import logger, helpers
from ape.services.log_service import registrar_log
from modules.permissoes import acesso_requerido
from datetime import datetime



ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp"
}

estoque_bp = Blueprint("estoque", __name__)


@estoque_bp.route("/escanear-inteligente", methods=["POST"])
@login_required
@acesso_requerido("estoque")
@limiter.limit("15 per minute")
def escanear_inteligente():

    try:

        # ====================================
        # CONTROLE DE PERMISSÃO
        # ====================================

        if current_user.role not in ["admin", "estoque"]:

            return jsonify({
                "status": "erro",
                "mensagem": "Acesso negado"
            }), 403

        # ====================================
        # LEITURA DO CÓDIGO DE BARRAS
        # ====================================

        codigo = request.form.get(
            "codigo_barras",
            ""
        ).strip()

        # ====================================
        # BUSCA POR CÓDIGO DE BARRAS
        # ====================================

        if codigo:

            if not codigo.isdigit():

                return jsonify({
                    "status": "erro",
                    "mensagem": "Código inválido"
                }), 400

            with get_conn() as con:

                with con.cursor() as cur:

                    cur.execute(
                        """
                        SELECT
                            id_produto,
                            nome
                        FROM produtos
                        WHERE codigo_barras = %s
                        """,
                        (codigo,)
                    )

                    produto = cur.fetchone()

            registrar_log("ESCANEAMENTO_ESTOQUE", "ESTOQUE", f"Código escaneado: {codigo}")

            if produto:

                return jsonify({
                    "status": "sucesso",
                    "acao": "adicionar",
                    "id_produto": produto[0],
                    "nome": produto[1]
                })

            return jsonify({
                "status": "novo",
                "acao": "cadastrar",
                "codigo_barras": codigo
            })

        # ====================================
        # PROCESSAMENTO POR IA
        # ====================================

        if "foto_produto" in request.files:

            file = request.files["foto_produto"]

            if not file.filename:

                return jsonify({
                    "status": "erro",
                    "mensagem": "Arquivo inválido"
                }), 400

            if file.content_type not in ALLOWED_MIME:

                return jsonify({
                    "status": "erro",
                    "mensagem": "Formato inválido"
                }), 400

            imagem_bytes = file.read()

            response = ai_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {
                                "inline_data": {
                                "mime_type": file.content_type or "image/jpeg",
                                "data": imagem_bytes
                                }
                            },
                            {
                                "text": "Identifique o nome comercial exato do produto nesta imagem. Retorne APENAS o nome, sem explicações."
                            }
                        ]
                    }
                ]
            )

            nome_id = (response.text or "").strip()

            nome_id = nome_id.replace("\n", " ")
            nome_id = nome_id[:120]

            if not nome_id:

                return jsonify({
                    "status": "erro",
                    "mensagem": "Produto não identificado"
                }), 422

            with get_conn() as con:

                with con.cursor() as cur:

                    cur.execute(
                        """
                        SELECT
                            id_produto,
                            nome
                        FROM produtos
                        WHERE nome ILIKE %s
                        LIMIT 1
                        """,
                        (f"{nome_id}%",)
                    )

                    similar = cur.fetchone()

            registrar_log("ESCANEAMENTO_ESTOQUE", "ESTOQUE", f"Código escaneado: {codigo}")

            if similar:

                return jsonify({
                    "status": "sucesso",
                    "acao": "adicionar",
                    "id_produto": similar[0],
                    "nome": similar[1],
                    "ia_detectou": nome_id
                })

            return jsonify({
                "status": "novo",
                "acao": "cadastrar",
                "nome_sugerido": nome_id
            })

        # ====================================
        # NENHUM DADO ENVIADO
        # ====================================

        return jsonify({
            "status": "erro",
            "mensagem": "Nenhum dado enviado"
        }), 400

    except Exception as e:

        logger.log_erro(
            f"Erro scanner inteligente: {e}"
        )

        return jsonify({
            "status": "erro",
            "mensagem": "Erro interno"
        }), 500

@estoque_bp.route("/estoque", methods=["GET"])
@login_required
def estoque_painel():
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                # Consulta de Matéria-Prima
                cur.execute("""
                    SELECT 
                        m.id_materia_prima, m.nome, m.unidade_medida, m.estoque_minimo,
                        COALESCE(SUM(CASE WHEN mov.tipo_movimento IN ('entrada','ajuste') 
                                          THEN mov.quantidade ELSE 0 END), 0)
                        - COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'saida' 
                                            THEN mov.quantidade ELSE 0 END), 0) AS estoque_atual,
                        CASE WHEN (
                            COALESCE(SUM(CASE WHEN mov.tipo_movimento IN ('entrada','ajuste') 
                                              THEN mov.quantidade ELSE 0 END), 0)
                            - COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'saida' 
                                                THEN mov.quantidade ELSE 0 END), 0)
                        ) <= m.estoque_minimo THEN 'BAIXO' ELSE 'OK' END AS status,
                        COALESCE(m.preco_unitario, 0),
                        TO_CHAR(m.data_cadastro, 'DD/MM/YYYY')
                    FROM materia_prima m
                    LEFT JOIN movimentacao_estoque mov ON m.id_materia_prima = mov.id_materia_prima
                    GROUP BY m.id_materia_prima, m.nome, m.unidade_medida, 
                             m.estoque_minimo, m.preco_unitario, m.data_cadastro
                    ORDER BY m.nome ASC
                """)
                materias = cur.fetchall()

                # Consulta de Subprodutos
                cur.execute("""
                    SELECT id_subproduto, nome, 0, preco_custo_unidade, 
                           unidade_medida, TO_CHAR(data_cadastro, 'DD/MM/YYYY')
                    FROM subprodutos ORDER BY nome ASC
                """)
                subprodutos = cur.fetchall()

                # Consulta de Produtos
                cur.execute("""
                    SELECT id_produto, nome, preco_venda, categoria, 0, 
                           TO_CHAR(data_cadastro, 'DD/MM/YYYY')
                    FROM produtos ORDER BY nome ASC
                """)
                lista_produtos = cur.fetchall()

        return render_template(
            "estoque.html",
            materias=materias, 
            subprodutos=subprodutos, 
            produtos=lista_produtos,
        )
    except Exception as e:
        logger.log_erro(f"Erro no painel de estoque: {e}")
        flash(f"Não foi possível carregar o painel de estoque: {e}", "danger")
        return redirect(url_for("main.dashboard"))

@estoque_bp.route("/previsao-estoque")
@login_required
def previsao_estoque():

    try:

        previsoes = estoque.previsao_demanda()

        return render_template(
            "previsao.html",
            previsoes=previsoes
        )

    except Exception as e:

        logger.log_erro(
            f"Erro previsão estoque: {e}"
        )

        flash(
            "Erro ao processar previsão",
            "danger"
        )

        return redirect(url_for("main.dashboard"))
    
@estoque_bp.route("/compras")
@login_required
def pagina_compras():
    return render_template("compras.html", materias=estoque.listar_materia_prima())

@estoque_bp.route("/registrar-producao", methods=["POST"])
@login_required
@acesso_requerido("estoque")
def registrar_producao():
    try:
        tipo_item   = request.form.get("tipo_item", "")
        id_item_raw = request.form.get("id_item", "")
        qtd_raw     = request.form.get("quantidade", "").strip()

        if not id_item_raw or not id_item_raw.isdigit():
            flash("ID do item inválido.", "danger")
            return redirect(url_for("estoque.estoque_painel"))

        id_item = int(id_item_raw)
        qtd = helpers._parse_float(qtd_raw)

        if qtd <= 0:
            flash("A quantidade deve ser maior que zero.", "warning")
            return redirect(url_for("estoque.estoque_painel"))

        if tipo_item == "subproduto":
            estoque.entrada_subproduto(id_item, qtd)
            registrar_log("PRODUCAO", "SUBPRODUTO", f"ID {id_item} | Qtd {qtd}")
        elif tipo_item == "produto":
            estoque.entrada_produto(id_item, qtd)
            registrar_log("PRODUCAO", "PRODUTO", f"ID {id_item} | Qtd {qtd}")
        else:
            flash("Tipo de item desconhecido.", "danger")
            return redirect(url_for("estoque.estoque_painel"))

        flash(f"Produção de {qtd} unidade(s) registrada com sucesso!", "success")
    except Exception as e:
        logger.log_erro(f"Erro ao registrar produção: {e}")
        flash(f"Erro ao processar produção: {e}", "danger")

    return redirect(url_for("estoque.estoque_painel"))

@estoque_bp.route("/estoque/fechamento")
@login_required
@acesso_requerido("estoque")
def fechamento_diario():
    dados_fechamento = estoque.obter_balanco_diario()
    return render_template("fechamento.html", balanco=dados_fechamento)

@estoque_bp.route("/estoque/balanco-diario")
@login_required
@acesso_requerido("estoque")
def balanco_diario_page():
    try:
        data_param = request.args.get("data", "").strip()
        if data_param:
            hoje_str = data_param
            try:
                ano, mes, dia = hoje_str.split("-")
                data_exibicao = f"{dia}/{mes}/{ano}"
            except ValueError:
                data_exibicao = hoje_str
        else:
            hoje_str = datetime.now().strftime("%Y-%m-%d")
            data_exibicao = datetime.now().strftime("%d/%m/%Y")

        lista_produtos = produtos.listar_todos() or []

        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT iv.id_produto, DATE(v.data_venda), SUM(iv.quantidade)
                    FROM itens_venda iv
                    JOIN vendas v ON v.id_venda = iv.id_venda
                    WHERE DATE(v.data_venda) = %s
                    GROUP BY iv.id_produto, DATE(v.data_venda)
                """, (hoje_str,))
                vendas_do_dia = {str(r[0]): int(r[2]) for r in cur.fetchall()}

        balanco = []
        for p in lista_produtos:
            id_produto, nome_produto = p[0], p[1]
            vendido_hoje = vendas_do_dia.get(str(id_produto), 0)
            balanco.append({
                "id": id_produto,
                "nome": nome_produto,
                "vendido": vendido_hoje,
            })

        return render_template(
            "balanco_diario.html",
            data_hoje=data_exibicao,
            data_busca_atual=hoje_str,
            datetime_hoje=datetime.now().strftime("%Y-%m-%d"),
            balanco=balanco,
        )
    except Exception as e:
        logger.log_erro(f"Erro no balanço diário: {e}")
        flash(f"Erro ao processar balanço diário: {e}", "danger")
        return redirect(url_for("estoque.estoque_painel"))
