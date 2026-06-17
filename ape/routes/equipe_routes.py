from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from utils.logger import log_erro
from modules import usuarios
from modules.planos import plano_requerido
from modules.permissoes import acesso_requerido

equipe_bp = Blueprint('equipe', __name__)

@equipe_bp.route("/equipe")
@login_required
@acesso_requerido("usuarios")
@plano_requerido("pro")
def gerenciar_equipe():

    try:

        lista_equipe = usuarios.listar_usuarios(current_user.id_empresa) or []
        return render_template("equipe.html", equipe=lista_equipe)

    except Exception as e:

        log_erro(f"Erro gerenciar_equipe: {e}")

        flash("Erro ao carregar equipe.", "danger")

        return redirect(url_for("main.dashboard"))
