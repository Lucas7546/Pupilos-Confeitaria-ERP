from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from modules import usuarios
from app.services.log_service import registrar_log
from utils.logger import log_erro
from modules.permissoes import acesso_requerido # Sua nova fonte da verdade
from werkzeug.security import generate_password_hash
from modules.db import get_conn # Importe seu get_conn aqui

usuarios_bp = Blueprint('usuarios', __name__)


@usuarios_bp.route("/usuarios")
@login_required
@acesso_requerido("usuarios")
def listar_usuarios_view():
    return render_template("usuarios.html", equipe=usuarios.listar_usuarios() or [])


@usuarios_bp.route("/excluir/<int:id>", methods=["POST"])
@login_required
@acesso_requerido("admin")
def deletar_user(id):
    if usuarios.excluir_usuario(id):
        flash("Usuário removido!", "success")
    else:
        flash("Erro ao remover usuário.", "danger")
    return redirect(url_for("usuarios.listar_usuarios_view"))

@usuarios_bp.route("/criar", methods=["POST"])
@login_required
@acesso_requerido("admin")
def criar_usuario():
    username = request.form.get("username", "").strip().lower()
    senha    = request.form.get("senha", "").strip()
    nivel    = request.form.get("nivel", "").strip().lower()

    if not username or not senha or not nivel:
        flash("Todos os campos são obrigatórios.", "warning")
        return redirect(url_for("usuarios.listar_usuarios_view"))

    if usuarios.criar_usuario(username, senha, nivel):
        registrar_log("CRIAR_USUARIO", "USUARIOS", f"{username} | Nível: {nivel}")
        flash(f"Usuário '{username}' criado!", "success")
    else:
        flash("Usuário já pode estar em uso.", "danger")
    return redirect(url_for("usuarios.listar_usuarios_view"))

@usuarios_bp.route("/editar/<int:id_usuario>", methods=["POST"])
@login_required
@acesso_requerido("admin") # Garante que só admin faz isso
def editar_usuario(id_usuario):
    nivel = request.form.get("nivel", "").strip().lower()
    nova_senha = request.form.get("nova_senha", "").strip()

    if usuarios.atualizar_usuario(id_usuario, nivel, nova_senha):
        registrar_log("EDIÇÃO", "USUARIOS", f"Perfil ID {id_usuario} atualizado")
        flash("Dados atualizados com sucesso!", "success")
    else:
        flash("Erro ao atualizar dados no banco.", "danger")

    return redirect(url_for("usuarios.listar_usuarios_view"))


@usuarios_bp.route("/toggle/<int:id_usuario>")
@login_required
@acesso_requerido("admin")
def toggle_usuario(id_usuario):
    # ... (lógica de buscar o status atual) ...

    # Usa a sua função que já existe!
    if usuarios.alterar_status(id_usuario, novo_status):
        flash("Status alterado com sucesso!", "success")
    else:
        flash("Erro ao alterar status no banco.", "danger")

    return redirect(url_for("usuarios.listar_usuarios_view"))
