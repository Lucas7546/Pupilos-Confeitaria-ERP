import sys
import os
sys.path.append('/opt/render/project/src')
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, login_required, current_user
from modules.auth import validar_login
from utils.logger import log_erro
from utils.helpers import registrar_acesso
from modules.permissoes import acesso_requerido
from ape.extensions import limiter
from ape.services.log_service import registrar_log
from modules.usuarios import atualizar_senha
from modules.planos import get_plano_empresa

auth_bp = Blueprint("auth", __name__)





# =============================================================
# LOGIN
# =============================================================

@auth_bp.route('/manual-lumenarch')
def manual():
    # Aqui você renderiza o seu guia-inicial.html
    return render_template('guia-inicial.html')

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip().lower()
        senha = request.form.get("senha", "").strip()

        try:

            user = validar_login(username, senha)

            if not user:
                flash("Usuário ou senha inválidos.", "danger")
                return render_template("login.html"), 401

            session.clear()
            login_user(user)

            # NOVO Registrar
            registrar_acesso(
                usuario=user.username,
                id_empresa=getattr(user, "id_empresa", None),
                empresa_nome=None,
                tipo="LOGIN"
            )

            session["user_id"] = user.id
            session["username"] = user.username
            session["nivel"] = user.nivel

            # ⚠️ NÃO definir empresa aqui
            session.pop("id_empresa", None)

            registrar_log(
                "LOGIN",
                "AUTH",
                f"Login realizado: {user.username}",
                user.username
            )

            flash(f"Bem-vindo, {user.username}!", "success")

            return redirect(url_for("main.dashboard"))

        except Exception as e:

            log_erro(f"Erro login: {e}")

            flash("Erro interno inesperado.", "danger")

            return render_template("login.html"), 500

    return render_template("login.html")



# =============================================================
# LOGOUT
# =============================================================
@auth_bp.route("/logout")
@login_required
def logout():

    try:

        registrar_log(
            "LOGOUT",
            "AUTH",
            f"Usuário '{current_user.username}' saiu",
            getattr(current_user, "username", "unknown")
        )

         # NOVO Registrar
        registrar_acesso(
            usuario=current_user.username,
            id_empresa=getattr(current_user, "id_empresa", None),
            empresa_nome=None,
            tipo="LOGOUT"
        )

    except Exception as e:
        log_erro(f"Erro ao registrar logout: {e}")

    try:
        logout_user()
    finally:
        session.clear()

    return redirect(url_for("auth.login"))


@auth_bp.route("/debug-user")
@login_required
@acesso_requerido("admin")
def debug_user():

    try:

        return {
            "id": current_user.id,
            "usuario": current_user.username,
            "nivel": current_user.nivel,
            "empresa": current_user.id_empresa
        }

    except Exception as e:

        log_erro(f"Erro debug_user: {e}")

        return {
            "erro": "falha ao obter usuário"
        }, 500
    


@auth_bp.route("/trocar-senha", methods=["POST"])
@login_required
def trocar_senha():
    nova_senha = request.form.get("nova_senha")

    if not nova_senha:
        flash("Informe uma nova senha.", "danger")
        return redirect(url_for("main.configuracoes"))

    atualizar_senha(current_user.id_usuario, nova_senha)

    flash("Senha alterada com sucesso!", "success")
    return redirect(url_for("main.configuracoes"))