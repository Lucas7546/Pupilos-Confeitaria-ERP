from flask import Blueprint, render_template, request, redirect, flash, url_for, g
from flask_login import login_required, current_user
from ape.extensions import limiter
import os
from modules.permissoes import acesso_requerido
import uuid
import tempfile
from ape.services.log_service import registrar_log
from utils.logger import log_erro
from modules.tenant_db import db_conn

from modules.ocr_notas import analisar_nota, limpar_e_parsear_json
from utils.helpers import validar_imagem_segura
from modules.ocr_notas import enriquecer_itens_nota


compras_bp = Blueprint("compras", __name__)


# =============================================================
# VIEW
# =============================================================
@compras_bp.route("/compras-inteligentes")
@login_required
@acesso_requerido("estoque")
@limiter.limit("10 per minute") # Limite do usuário
@limiter.limit("50 per hour", key_func=lambda: f"empresa:{g.id_empresa}")# Limite da empresa
def compras_inteligentes():
    return render_template("compras_inteligentes.html")


# =============================================================
# OCR NOTA FISCAL
# =============================================================
@compras_bp.route("/processar-nota", methods=["POST"])
@login_required
@acesso_requerido("estoque")
@limiter.limit("10 per minute") # Limite do usuário
@limiter.limit("50 per hour", key_func=lambda: f"empresa:{g.id_empresa}") # Limite da empresa
def processar_nota():

    caminho_imagem = None

    try:

        foto = request.files.get("foto_nota")

        if not foto or not foto.filename:
            flash("Nenhuma imagem enviada.", "danger")
            return redirect(url_for("compras.compras_inteligentes"))

        extensao = os.path.splitext(foto.filename)[1].lower()

        if extensao not in (".jpg", ".jpeg", ".png", ".webp"):
            flash("Formato inválido.", "danger")
            return redirect(url_for("compras.compras_inteligentes"))

        if not validar_imagem_segura(foto):
            flash("Imagem inválida.", "danger")
            return redirect(url_for("compras.compras_inteligentes"))

        # =========================
        # ARQUIVO TEMPORÁRIO SEGURO
        # =========================
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=extensao)
        caminho_imagem = tmp.name
        foto.save(caminho_imagem)

        tamanho_mb = os.path.getsize(caminho_imagem) / (1024 * 1024)

        if tamanho_mb > 18:
            flash("Imagem muito grande (máx 18MB).", "danger")
            return redirect(url_for("compras.compras_inteligentes"))

        # =========================
        # IA OCR
        # =========================
        resposta_raw = analisar_nota(caminho_imagem)

        if not resposta_raw:
            flash("IA não conseguiu ler a nota.", "danger")
            return redirect(url_for("compras.compras_inteligentes"))

        itens = limpar_e_parsear_json(resposta_raw)

        itens = enriquecer_itens_nota(itens)

        if not itens:
            log_erro(f"OCR inválido: {resposta_raw[:300]}")
            flash("Erro ao interpretar nota fiscal.", "danger")
            return redirect(url_for("compras.compras_inteligentes"))

        registrar_log(
            "OCR_NOTA",
            "COMPRAS",
            f"{len(itens)} itens extraídos",
            current_user.username
        )

        return render_template(
            "resultado_nota.html",
            itens=itens,
            total_itens=len(itens)
        )

    except Exception as e:
        log_erro(f"Erro OCR nota: {e}")
        flash("Erro interno ao processar nota.", "danger")
        return redirect(url_for("compras.compras_inteligentes"))

    finally:
        if caminho_imagem and os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)


# =============================================================
# CONFIRMAÇÃO (GRAVAÇÃO NO BANCO)
# =============================================================
@compras_bp.route("/confirmar-nota", methods=["POST"])
@login_required
@acesso_requerido("estoque")
@limiter.limit("10 per minute")
@limiter.limit(
    "50 per hour",
    key_func=lambda: f"empresa:{g.id_empresa}"
)
def confirmar_nota():

    try:

        total = request.form.get("total_itens", "0")

        try:
            total = int(total)
        except:
            total = 0

        if total <= 0:
            flash("Nenhum item para confirmar.", "warning")
            return redirect(url_for("compras.compras_inteligentes"))

        salvos = 0
        erros = []

        with db_conn() as conn:

            with conn.cursor() as cur:

                for i in range(min(total, 100)):

                    nome = request.form.get(f"nome_{i}", "").strip()

                    try:
                        qtd = float(
                            request.form.get(f"qtd_{i}", 0) or 0
                        )

                        preco = float(
                            request.form.get(f"preco_{i}", 0) or 0
                        )

                    except:
                        continue

                    unidade = request.form.get(
                        f"unidade_{i}",
                        "UN"
                    ).upper()

                    if not nome or qtd <= 0:
                        continue

                    # =========================
                    # BUSCA MATÉRIA PRIMA
                    # =========================

                    cur.execute(
                        """
                        SELECT id_materia_prima
                        FROM materia_prima
                        WHERE LOWER(nome) = LOWER(%s)
                        AND id_empresa = %s
                        LIMIT 1
                        """,
                        (
                            nome,
                            current_user.id_empresa
                        )
                    )

                    materia = cur.fetchone()

                    if materia:

                        id_materia = materia[0]

                        if preco > 0:

                            cur.execute(
                                """
                                UPDATE materia_prima
                                SET preco_unitario = %s,
                                    unidade_medida = %s
                                WHERE id_materia_prima = %s
                                AND id_empresa = %s
                                """,
                                (
                                    preco,
                                    unidade,
                                    id_materia,
                                    current_user.id_empresa
                                )
                            )

                    else:

                        cur.execute(
                            """
                            INSERT INTO materia_prima
                            (
                                nome,
                                unidade_medida,
                                preco_unitario,
                                estoque_minimo,
                                id_empresa
                            )
                            VALUES
                            (
                                %s,
                                %s,
                                %s,
                                0,
                                %s
                            )
                            RETURNING id_materia_prima
                            """,
                            (
                                nome,
                                unidade,
                                preco,
                                current_user.id_empresa
                            )
                        )

                        id_materia = cur.fetchone()[0]

                    # =========================
                    # MOVIMENTAÇÃO ESTOQUE
                    # =========================

                    cur.execute(
                        """
                        INSERT INTO movimentacao_estoque
                        (
                            id_materia_prima,
                            tipo_movimento,
                            quantidade,
                            observacao,
                            usuario,
                            id_empresa
                        )
                        VALUES
                        (
                            %s,
                            'entrada',
                            %s,
                            'OCR nota fiscal',
                            %s,
                            %s
                        )
                        """,
                        (
                            id_materia,
                            qtd,
                            current_user.username,
                            current_user.id_empresa
                        )
                    )

                    salvos += 1


        registrar_log(
            "CONFIRMAR_NOTA",
            "COMPRAS",
            f"{salvos} itens importados via OCR",
            current_user.username
        )

        flash(
            f"{salvos} itens adicionados com sucesso!",
            "success"
        )

        return redirect(
            url_for("estoque.previsao_estoque")
        )

    except Exception as e:

        log_erro(f"Erro confirmar nota: {e}")

        flash(
            "Erro ao salvar nota.",
            "danger"
        )

        return redirect(
            url_for("compras.compras_inteligentes")
        )