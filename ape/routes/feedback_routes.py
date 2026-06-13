from flask import Blueprint, request, redirect, flash, url_for, g, render_template
from modules.tenant_db import db_conn 
from flask_login import current_user, login_required 
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
                    INSERT INTO feedback (id_empresa, usuario_origem, tipo, mensagem)
                    VALUES (%s, %s, %s, %s)
                """, (g.id_empresa, current_user.username, tipo, mensagem))
                conn.commit() # Garante que a inserção seja salva
                
        flash("Obrigado pelo seu feedback! Vamos analisar.", "success")
    except Exception as e:
        log_erro(f"Erro ao salvar feedback: {e}")
        flash("Erro ao enviar feedback, tente novamente mais tarde.", "danger")
        
    redirect(url_for("main.dashboard"))


@feedback_bp.route("/painel-feedback")
@login_required # Ou coloque um check de admin aqui
def listar_feedbacks():
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM feedback ORDER BY data_criacao DESC")
            feedbacks = cur.fetchall()
    return render_template("admin_feedback.html", feedbacks=feedbacks)