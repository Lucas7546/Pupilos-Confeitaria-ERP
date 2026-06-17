from flask import Blueprint, request, redirect, flash, url_for, g, render_template
from modules.tenant_db import db_conn, db_admin_conn
from flask_login import current_user, login_required 
from modules.decorators import superadmin_required
from utils.logger import log_erro # Importante para logs

# O nome do blueprint deve ser igual à variável que você usa no @route
feedback_bp = Blueprint("feedback", __name__)

@feedback_bp.route("/enviar-feedback", methods=["POST"])
@login_required
def enviar_feedback():

    tipo = request.form.get("tipo")
    mensagem = request.form.get("mensagem", "").strip()

    if not mensagem:
        flash("A mensagem não pode estar vazia.", "warning")
        return redirect(url_for("main.dashboard"))

    try:

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO feedback
                    (
                        id_empresa,
                        usuario_origem,
                        tipo,
                        mensagem
                    )
                    VALUES (%s, %s, %s, %s)
                """, (
                    g.id_empresa,
                    current_user.username,
                    tipo,
                    mensagem
                ))

        flash(
            "Obrigado pelo seu feedback! Vamos analisar.",
            "success"
        )

    except Exception as e:

        log_erro(
            f"Erro ao salvar feedback: {e}"
        )

        flash(
            "Erro ao enviar feedback, tente novamente mais tarde.",
            "danger"
        )

    return redirect(url_for("main.dashboard"))

@feedback_bp.route("/painel-feedback")
@login_required # Ou coloque um check de admin aqui
def listar_feedbacks():
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM feedback ORDER BY data_criacao DESC")
            feedbacks = cur.fetchall()
    return render_template("admin_feedback.html", feedbacks=feedbacks)


@feedback_bp.route("/feedback/<int:id_feedback>/status", methods=["POST"])
@login_required
@superadmin_required
def atualizar_status_feedback(id_feedback):

    novo_status = request.form.get("status")

    try:

        with db_admin_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE feedback
                    SET status = %s
                    WHERE id_feedback = %s
                    """,
                    (
                        novo_status,
                        id_feedback
                    )
                )

                conn.commit()

        flash(
            "Status atualizado com sucesso.",
            "success"
        )

    except Exception as e:

        log_erro(
            f"Erro ao atualizar feedback {id_feedback}: {e}"
        )

        flash(
            "Erro ao atualizar status.",
            "danger"
        )

    return redirect(
        url_for("auditoria.listar_solicitacoes")
    )



@feedback_bp.route("/feedback/<int:id_feedback>/responder", methods=["POST"])
@login_required
@superadmin_required
def responder_feedback(id_feedback):

    resposta = request.form.get("resposta_admin")

    try:

        with db_admin_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE feedback
                    SET resposta_admin = %s
                    WHERE id_feedback = %s
                    """,
                    (
                        resposta,
                        id_feedback
                    )
                )

        flash(
            "Resposta enviada com sucesso.",
            "success"
        )

    except Exception as e:

        log_erro(
            f"Erro ao responder feedback {id_feedback}: {e}"
        )

        flash(
            "Erro ao salvar resposta.",
            "danger"
        )

    return redirect(
        url_for("auditoria.listar_solicitacoes")
    )