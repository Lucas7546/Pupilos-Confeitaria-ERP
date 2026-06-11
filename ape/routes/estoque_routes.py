from flask import ( Blueprint, request, jsonify, render_template, flash, redirect, url_for, session)
from flask_login import login_required, current_user
from ape.extensions import limiter
from ape.services import ai_client
from modules.tenant_db import db_conn
from modules import estoque, produtos
from utils import logger, helpers
from ape.services.log_service import registrar_log
from modules.permissoes import acesso_requerido
from datetime import datetime
from flask import g




ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp"
}

estoque_bp = Blueprint("estoque", __name__)


@estoque_bp.before_request
def carregar_tenant_estoque():
    if not getattr(g, "id_empresa", None):
        print("DEBUG: estoque sem tenant no g.id_empresa")

@estoque_bp.route("/compras")
@login_required
def pagina_compras():
    return render_template("compras.html", materias=estoque.listar_materia_prima())

@estoque_bp.route("/registrar-producao", methods=["POST"])
@login_required
@acesso_requerido("estoque")
@limiter.limit("10 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
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

@estoque_bp.route("/escanear-inteligente", methods=["POST"])
@login_required
@acesso_requerido("estoque")
@limiter.limit("10 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
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

            with db_conn() as conn:

                with conn.cursor() as cur:

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

            with db_conn() as conn:

                with conn.cursor() as cur:

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
@limiter.limit("20 per minute")
@limiter.limit("150 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}")
def estoque_painel():

    try:

        with db_conn() as conn:
            with conn.cursor() as cur:

                # ==========================
                # MATÉRIA PRIMA
                # ==========================
                cur.execute("""
                    SELECT
                        m.id_materia_prima,
                        m.nome,
                        m.unidade_medida,
                        m.estoque_minimo,

                        COALESCE(
                            SUM(
                                CASE
                                    WHEN mov.tipo_movimento IN ('entrada','ajuste')
                                    THEN mov.quantidade
                                    ELSE 0
                                END
                            ),0
                        )
                        -
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN mov.tipo_movimento = 'saida'
                                    THEN mov.quantidade
                                    ELSE 0
                                END
                            ),0
                        ) AS estoque_atual,

                        CASE
                            WHEN (
                                COALESCE(
                                    SUM(
                                        CASE
                                            WHEN mov.tipo_movimento IN ('entrada','ajuste')
                                            THEN mov.quantidade
                                            ELSE 0
                                        END
                                    ),0
                                )
                                -
                                COALESCE(
                                    SUM(
                                        CASE
                                            WHEN mov.tipo_movimento = 'saida'
                                            THEN mov.quantidade
                                            ELSE 0
                                        END
                                    ),0
                                )
                            ) <= m.estoque_minimo
                            THEN 'BAIXO'
                            ELSE 'OK'
                        END AS status,

                        COALESCE(m.preco_unitario,0),

                        TO_CHAR(
                            m.data_cadastro,
                            'DD/MM/YYYY'
                        )

                    FROM materia_prima m

                    LEFT JOIN movimentacao_estoque mov
                        ON mov.id_materia_prima = m.id_materia_prima
                        AND mov.id_empresa = m.id_empresa

                    WHERE m.id_empresa = %s

                    GROUP BY
                        m.id_materia_prima,
                        m.nome,
                        m.unidade_medida,
                        m.estoque_minimo,
                        m.preco_unitario,
                        m.data_cadastro

                    ORDER BY m.nome ASC
                """, (current_user.id_empresa,))

                materias = cur.fetchall()

                # ==========================
                # SUBPRODUTOS
                # ==========================
                cur.execute("""
                    SELECT
                        id_subproduto,
                        nome,
                        0,
                        preco_custo_unidade,
                        unidade_medida,
                        TO_CHAR(data_cadastro,'DD/MM/YYYY')

                    FROM subprodutos

                    WHERE id_empresa = %s

                    ORDER BY nome ASC
                """, (current_user.id_empresa,))

                subprodutos = cur.fetchall()

                # ==========================
                # PRODUTOS
                # ==========================
                cur.execute("""
                    SELECT
                        id_produto,
                        nome,
                        preco_venda,
                        categoria,
                        0,
                        TO_CHAR(data_cadastro,'DD/MM/YYYY')

                    FROM produtos

                    WHERE id_empresa = %s

                    ORDER BY nome ASC
                """, (current_user.id_empresa,))

                lista_produtos = cur.fetchall()

        return render_template(
            "estoque.html",
            materias=materias,
            subprodutos=subprodutos,
            produtos=lista_produtos
        )

    except Exception as e:
        logger.log_erro(f"Erro no painel de estoque: {e}")
        flash(
            f"Não foi possível carregar o painel de estoque: {e}",
            "danger"
        )
        return redirect(url_for("main.dashboard"))

@estoque_bp.route("/previsao-estoque")
@login_required
def previsao_estoque():

    try:

        previsoes = estoque.previsao_demanda(current_user.id_empresa)

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
    print("BALANCO_DIARIO_VERSAO_NOVA")
    
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

        with db_conn() as conn:

            with conn.cursor() as cur:

                # =====================================
                # VENDAS DO DIA
                # =====================================

                cur.execute("""
                    SELECT
                        iv.id_produto,
                        COALESCE(SUM(iv.quantidade),0)
                    FROM itens_venda iv
                    JOIN vendas v
                        ON v.id_venda = iv.id_venda
                    WHERE DATE(v.data_venda) = %s
                    GROUP BY iv.id_produto
                """, (hoje_str,))

                vendas_dia = {
                    int(r[0]): int(r[1])
                    for r in cur.fetchall()
                }

                # =====================================
                # PRODUÇÃO DO DIA
                # =====================================

                cur.execute("""
                    SELECT
                        produto_id,
                        COALESCE(SUM(quantidade),0)
                    FROM movimentacao_produtos
                    WHERE tipo = 'entrada'
                    AND DATE(data) = %s
                    GROUP BY produto_id
                """, (hoje_str,))

                producao_dia = {
                    int(r[0]): int(r[1])
                    for r in cur.fetchall()
                }

                # =====================================
                # SALDO ATUAL
                # =====================================

                cur.execute("""
                    SELECT
                        p.id_produto,
                        p.nome,

                        COALESCE(
                            SUM(
                                CASE
                                    WHEN mp.tipo = 'entrada'
                                        THEN mp.quantidade
                                    ELSE 0
                                END
                            ),0
                        )
                        -
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN mp.tipo = 'saida'
                                        THEN mp.quantidade
                                    ELSE 0
                                END
                            ),0
                        ) AS saldo

                    FROM produtos p

                    LEFT JOIN movimentacao_produtos mp
                        ON p.id_produto = mp.produto_id

                    GROUP BY
                        p.id_produto,
                        p.nome

                    ORDER BY p.nome
                """)

                produtos_saldo = cur.fetchall()

        balanco = []

        total_vendido = 0
        total_produzido = 0
        total_saldo = 0

        for produto in produtos_saldo:

            id_produto = produto[0]
            nome_produto = produto[1]
            saldo_atual = int(produto[2] or 0)

            produzido = producao_dia.get(id_produto, 0)
            vendido = vendas_dia.get(id_produto, 0)

            total_vendido += vendido
            total_produzido += produzido
            total_saldo += saldo_atual

            balanco.append({

                "id": id_produto,
                "nome": nome_produto,

                "produzido": produzido,
                "vendido": vendido,
                "saldo": saldo_atual,

                "status":
                    "baixo"
                    if saldo_atual <= 5
                    else "ok"

            })

        registrar_log(
            "BALANCO_DIARIO",
            "ESTOQUE",
            f"Balanço consultado para {hoje_str}"
        )

        return render_template(

            "balanco_diario.html",

            data_hoje=data_exibicao,
            data_busca_atual=hoje_str,
            datetime_hoje=datetime.now().strftime("%Y-%m-%d"),

            balanco=balanco,

            total_produtos=len(balanco),
            total_vendido=total_vendido,
            total_produzido=total_produzido,
            total_saldo=total_saldo

        )

    except Exception as e:

        logger.log_erro(
            f"Erro no balanço diário: {e}"
        )

        flash(
            f"Erro ao processar balanço diário: {e}",
            "danger"
        )

        return redirect(
            url_for("estoque.estoque_painel")
        )