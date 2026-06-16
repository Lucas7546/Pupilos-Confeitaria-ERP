# Imports do Flask
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required 

# Seus módulos internos
from modules import usuarios   
from modules.decorators import limite_usuarios_required                         
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
from utils.logger import log_erro
from werkzeug.security import generate_password_hash
from modules.tenant_db import db_conn, db_admin_conn
from flask_login import current_user

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
    if usuarios.excluir_usuario(id, current_user.id_empresa):
        registrar_log(
            "EXCLUIR_USUARIO",
            "USUARIOS",
            f"ID {id} removido",
            current_user.username
        )
        flash("Usuário removido!", "success")
    else:
        flash("Erro ao remover usuário.", "danger")

    return redirect(url_for("usuarios.listar_usuarios_view"))

@usuarios_bp.route("/criar", methods=["POST"])
@login_required
@acesso_requerido("admin")
@limite_usuarios_required
def criar_usuario():
    username = request.form.get("username", "").strip().lower()
    senha    = request.form.get("senha", "").strip()
    nivel    = request.form.get("nivel", "").strip().lower()

    if not username or not senha or not nivel:
        flash("Todos os campos são obrigatórios.", "warning")
        return redirect(url_for("usuarios.listar_usuarios_view"))

    if usuarios.criar_usuario(username, senha, nivel):
        registrar_log("CRIAR_USUARIO", "USUARIOS", f"{username} | Nível: {nivel}", current_user.username)
        flash(f"Usuário '{username}' criado!", "success")
    else:
        flash("Usuário já pode estar em uso.", "danger")
    return redirect(url_for("usuarios.listar_usuarios_view"))

@usuarios_bp.route("/editar/<int:id_usuario>", methods=["POST"])
@login_required
@acesso_requerido("admin")
def editar_usuario(id_usuario):
    nivel = request.form.get("nivel", "").strip().lower()
    nova_senha = request.form.get("nova_senha", "").strip()

    if usuarios.atualizar_usuario(id_usuario, nivel, nova_senha):
        registrar_log("EDIÇÃO", "USUARIOS", f"Perfil ID {id_usuario} atualizado", current_user.username)
        flash("Dados atualizados com sucesso!", "success")
    else:
        flash("Erro ao atualizar dados no banco.", "danger")

    return redirect(url_for("usuarios.listar_usuarios_view"))


@usuarios_bp.route("/toggle/<int:id_usuario>")
@login_required
@acesso_requerido("admin")
def toggle_usuario(id_usuario):
    usuario = usuarios.buscar_usuario_id(id_usuario, current_user.id_empresa)
    if not usuario:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("usuarios.listar_usuarios_view"))

    ativo_atual = int(usuario[4] if len(usuario) > 4 else 1)
    novo_status = 0 if ativo_atual == 1 else 1

    if usuarios.alterar_status(id_usuario, novo_status):
        status_txt = "ativado" if novo_status == 1 else "desativado"
        registrar_log("ALTERAR_STATUS", "USUARIOS", f"ID {id_usuario} {status_txt}", current_user.username)
        flash(f"Conta {status_txt} com sucesso!", "success")
    else:
        flash("Falha ao atualizar status.", "danger")

    return redirect(url_for("usuarios.listar_usuarios_view"))


@usuarios_bp.route("/admin/config")
@login_required
@acesso_requerido("admin")
def area_admin():
    lista = usuarios.listar_usuarios() or []
    
    # Adicionando a busca pelo número de pendências
    count_pendentes = 0
    try:
        with db_admin_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM solicitacoes_upgrade WHERE status = 'pendente'")
                resultado = cur.fetchone()
                if resultado:
                    count_pendentes = resultado[0]
    except Exception as e:
        print(f"Erro ao contar pendências: {e}")

    return render_template(
        "admin_panel.html", 
        total_usuarios=len(lista), 
        usuarios=lista,
        count_pendentes=count_pendentes # Passa para o HTML
    )

@usuarios_bp.route("/editar/<int:id_usuario>", methods=["GET"])
@login_required
@acesso_requerido("admin")
def editar_usuario_page(id_usuario):

    usuario = usuarios.buscar_usuario_id(id_usuario, current_user.id_empresa)

    if not usuario:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("usuarios.area_admin"))

    return render_template(
        "editar_usuario.html",
        usuario=usuario
    )

@usuarios_bp.route("/novo")
@login_required
@acesso_requerido("admin")
@limite_usuarios_required
def novo_usuario():
    return render_template("novo_usuario.html")

