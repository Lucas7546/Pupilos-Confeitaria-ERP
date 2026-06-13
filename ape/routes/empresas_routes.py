from flask import Blueprint, request, redirect, flash, url_for, render_template, g
from flask_login import login_required
from modules.tenant_db import db_conn
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

    codigo_convite = request.form.get("codigo_convite", "").strip().upper()

    # =========================
    # VALIDAÇÕES BÁSICAS
    # =========================
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

        # =========================
        # VALIDAR CONVITE
        # =========================
        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT id
                    FROM convites_empresa
                    WHERE codigo = %s
                      AND utilizado = FALSE
                    LIMIT 1
                """, (codigo_convite,))

                convite = cur.fetchone()

        if not convite:
            return redirect(url_for("empresas.convite_invalido"))

        # =========================
        # CRIAR EMPRESA
        # =========================
        id_empresa = criar_empresa(
            nome=nome_empresa,
            responsavel=responsavel,
            plano=plano
        )

        # =========================
        # CRIAR USUÁRIO DONO
        # =========================
        criar_usuario_empresa(
            username=username,
            senha=senha,
            nivel="dono",
            id_empresa=id_empresa
        )

        # =========================
        # MARCAR CONVITE COMO USADO
        # =========================
        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    UPDATE convites_empresa
                    SET utilizado = TRUE
                    WHERE codigo = %s
                      AND utilizado = FALSE
                """, (codigo_convite,))


        # =========================
        # SUCESSO
        # =========================
        flash("Empresa criada com sucesso. Faça seu login!", "success")
        return redirect(url_for("auth.login"))

    except Exception as e:

        log_erro(f"Erro no cadastro da empresa {nome_empresa}: {e}")

        flash("Erro interno ao criar empresa.", "danger")
        return redirect(url_for("auth.login"))
    


@empresas_bp.route("/convite-invalido")
def convite_invalido():
    return render_template("convite_invalido.html")



@empresas_bp.route("/configuracoes")
@login_required
def configuracoes():
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                # Busca o plano
                cur.execute("SELECT plano FROM empresas WHERE id_empresa = %s", (g.id_empresa,))
                resultado = cur.fetchone()
                plano_atual = resultado[0] if resultado else "basic"
                
                # Busca os feedbacks da empresa
                cur.execute("SELECT * FROM feedback WHERE id_empresa = %s ORDER BY data_criacao DESC", (g.id_empresa,))
                feedbacks = cur.fetchall()
                
        return render_template("configuracoes.html", plano=plano_atual, feedbacks=feedbacks)
    except Exception as e:
        log_erro(f"Erro ao carregar configurações: {e}")
        flash("Erro ao carregar painel de configurações.", "danger")
        return redirect(url_for("main.dashboard"))
    
@empresas_bp.route("/upgrade-necessario")
@login_required
def upgrade_necessario():
    return render_template("upgrade.html")