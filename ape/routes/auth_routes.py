import sys
import os
sys.path.append('/opt/render/project/src')
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, login_required, current_user
from modules.auth import validar_login, User
from utils.logger import log_erro
from modules.permissoes import acesso_requerido
from ape.extensions import limiter
from ape.services.log_service import registrar_log


auth_bp = Blueprint("auth", __name__)


# =============================================================
# LOGIN
# =============================================================
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

            # proteção contra session fixation
            session.clear()

            login_user(user)

            session["user_id"] = user.id
            session["username"] = user.username
            session["nivel"] = user.nivel

            registrar_log(
                "LOGIN",
                "AUTH",
                f"Usuário '{user.username}' autenticado"
            )

            flash(f"Bem-vindo, {user.username}!", "success")

            # IMPORTANTE: manter string direta até o blueprint principal existir
            return redirect(url_for("main.dashboard"))

        except Exception as e:
            log_erro(f"Erro crítico no login: {e}")
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
            f"Usuário '{current_user.username}' saiu"
        )
    except Exception as e:
        log_erro(f"Erro ao registrar logout: {e}")

    logout_user()
    session.clear()

    return redirect(url_for("auth.login"))