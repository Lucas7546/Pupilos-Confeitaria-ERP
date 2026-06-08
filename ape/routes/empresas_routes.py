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


@empresas_bp.route(
    "/cadastro-empresa",
    methods=["POST"]
)
def cadastro_empresa():

    nome_empresa = request.form.get(
        "empresa",
        ""
    ).strip()

    responsavel = request.form.get(
        "responsavel",
        ""
    ).strip()

    username = request.form.get(
        "username",
        ""
    ).strip().lower()

    senha = request.form.get(
        "senha",
        ""
    ).strip()

    plano = request.form.get(
        "plano",
        "basic"
    )

    if not nome_empresa:

        flash(
            "Informe o nome da empresa.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    if not responsavel:

        flash(
            "Informe o responsável.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    if not username:

        flash(
            "Informe o usuário.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    if len(senha) < 6:

        flash(
            "Senha deve ter pelo menos 6 caracteres.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    if buscar_usuario(username):

        flash(
            "Usuário já existe.",
            "warning"
        )

        return redirect(
            url_for("auth.login")
        )

    conn = get_conn()

    try:

        with conn:

            id_empresa = criar_empresa(
                nome=nome_empresa,
                responsavel=responsavel,
                plano=plano,
                conn=conn
            )

            criar_usuario_empresa(
                username=username,
                senha=senha,
                nivel="dono",
                id_empresa=id_empresa,
                conn=conn
            )

        flash(
            "Empresa criada com sucesso. Faça login.",
            "success"
        )

        return redirect(
            url_for("auth.login")
        )

    except Exception as e:

        log_erro(
            f"Erro cadastro empresa: {e}"
        )

        flash(
            "Erro ao criar empresa.",
            "danger"
        )

        return redirect(
            url_for("auth.login")
        )

    finally:

        conn.close()