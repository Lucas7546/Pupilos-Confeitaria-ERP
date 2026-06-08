from flask import Blueprint, request, redirect, flash, url_for

from modules.db import get_conn
from modules.empresas import criar_empresa
from modules.usuarios import (
    criar_usuario_empresa,
    buscar_usuario
)

from utils.logger import log_erro


empresas_bp = Blueprint(
    "empresas",
    __name__
)


@empresas_bp.route("/cadastro-empresa", methods=["POST"])
def cadastro_empresa():

    nome_empresa = request.form.get("empresa", "").strip()
    responsavel = request.form.get("responsavel", "").strip()
    username = request.form.get("username", "").strip().lower()
    senha = request.form.get("senha", "").strip()
    plano = request.form.get("plano", "basic")

    if not nome_empresa or not responsavel or not username:
        flash("Preencha todos os campos obrigatórios.", "danger")
        return redirect(url_for("auth.login"))

    if len(senha) < 6:
        flash("A senha deve ter pelo menos 6 caracteres.", "danger")
        return redirect(url_for("auth.login"))

    if buscar_usuario(username):
        flash("Este nome de usuário já está em uso.", "warning")
        return redirect(url_for("auth.login"))

    try:
        # 1. empresa
        id_empresa = criar_empresa(
            nome=nome_empresa,
            responsavel=responsavel,
            plano=plano
        )

        # 2. usuário dono
        criar_usuario_empresa(
            username=username,
            senha=senha,
            nivel="dono",
            id_empresa=id_empresa
        )

        flash("Empresa criada com sucesso. Faça seu login!", "success")
        return redirect(url_for("auth.login"))

    except Exception as e:
        log_erro(f"Erro no cadastro da empresa {nome_empresa}: {e}")
        flash("Erro interno ao criar empresa. Tente novamente mais tarde.", "danger")
        return redirect(url_for("auth.login"))