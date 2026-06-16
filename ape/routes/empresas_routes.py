from flask import Blueprint, request, redirect, flash, url_for, render_template, g
from flask_login import login_required, current_user
from modules.tenant_db import db_conn
from modules.empresas import criar_empresa
from modules.usuarios import (criar_usuario_empresa, buscar_usuario)
from utils.logger import log_erro
from modules.decorators import superadmin_required
from psycopg2.extras import DictCursor


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

    try:

        with db_conn() as conn:
            with conn.cursor() as cur:

                # =========================
                # RESERVA O CONVITE
                # =========================

                cur.execute("""
                    UPDATE convites_empresa
                    SET utilizado = TRUE
                    WHERE codigo = %s
                      AND utilizado = FALSE
                    RETURNING id
                """, (codigo_convite,))

                convite = cur.fetchone()

                if not convite:
                    flash("Convite inválido ou já utilizado.", "danger")
                    return redirect(url_for("empresas.convite_invalido"))

                # =========================
                # VERIFICA USUÁRIO
                # =========================

                cur.execute("""
                    SELECT 1
                    FROM usuarios
                    WHERE LOWER(username) = LOWER(%s)
                    LIMIT 1
                """, (username,))

                if cur.fetchone():
                    flash("Este nome de usuário já está em uso.", "warning")
                    return redirect(url_for("auth.login"))

                # =========================
                # CRIA EMPRESA + PLANO
                # =========================

                id_empresa = criar_empresa(
                    nome=nome_empresa,
                    responsavel=responsavel,
                    plano=plano,
                    cursor=cur
                )

                # =========================
                # CRIA USUÁRIO DONO
                # =========================

                criar_usuario_empresa(
                    username=username,
                    senha=senha,
                    nivel="dono",
                    id_empresa=id_empresa,
                    cursor=cur
                )

                # =========================
                # ATUALIZA DADOS DO CONVITE
                # =========================

                cur.execute("""
                    UPDATE convites_empresa
                    SET
                        id_empresa_usada = %s,
                        nome_empresa_usada = %s,
                        nome_responsavel_usado = %s
                    WHERE id = %s
                """, (
                    id_empresa,
                    nome_empresa,
                    responsavel,
                    convite[0]
                ))

                conn.commit()

        flash(
            "Empresa criada com sucesso. Faça seu login!",
            "success"
        )

        return redirect(url_for("auth.login"))

    except Exception as e:

        log_erro(
            f"Erro no cadastro da empresa "
            f"{nome_empresa} ({codigo_convite}): {e}"
        )

        flash(
            "Erro interno ao criar empresa. Tente novamente.",
            "danger"
        )

        return redirect(url_for("auth.login"))


@empresas_bp.route("/convite-invalido")
def convite_invalido():
    return render_template("convite_invalido.html")



@empresas_bp.route("/configuracoes")
@login_required
def configuracoes():
    try:
        with db_conn() as conn:
            # Note o cursor_factory=DictCursor aqui!
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # 1. Busca o plano
                cur.execute("SELECT plano FROM empresas WHERE id_empresa = %s", (g.id_empresa,))
                resultado = cur.fetchone()
                plano_atual = resultado['plano'] if resultado else "basic"
                
                # 2. Busca os feedbacks usando nomes de colunas explícitos
                cur.execute("""
                    SELECT id, id_empresa, usuario, tipo, mensagem, status, data_criacao 
                    FROM feedback 
                    WHERE id_empresa = %s 
                    ORDER BY data_criacao DESC
                """, (g.id_empresa,))
                feedbacks = cur.fetchall()
                
        return render_template("configuracoes.html", plano_atual=plano_atual, feedbacks=feedbacks)
    except Exception as e:
        log_erro(f"Erro configuracoes: {e}")
        return "Erro ao carregar configurações", 500
    
@empresas_bp.route("/upgrade-necessario")
@login_required
def upgrade():
    return render_template("upgrade.html")


@empresas_bp.route("/excluir-convite/<int:id_convite>", methods=["POST"])
@login_required
@superadmin_required
def excluir_convite(id_convite):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM convites_empresa WHERE id = %s AND utilizado = FALSE", (id_convite,))
            conn.commit()
    flash("Convite removido com sucesso.", "info")
    # CORREÇÃO AQUI: redirecionar para a listagem
    return redirect(url_for('empresas.lista_convites'))

@empresas_bp.route("/lista-convites")
@login_required
@superadmin_required
def lista_convites():

    with db_conn() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    id,
                    codigo,
                    utilizado,
                    criado_em,
                    nome_empresa_usada,
                    nome_responsavel_usado,
                    id_empresa_usada
                FROM convites_empresa
                ORDER BY utilizado ASC, criado_em DESC
            """)

            convites = cur.fetchall()

    return render_template("admin_convites.html", convites=convites)


@empresas_bp.route("/excluir-empresa/<int:id_empresa>", methods=["POST"])
@login_required
@superadmin_required
def excluir_empresa(id_empresa):
    # Lógica de exclusão que definimos antes
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM convites_empresa WHERE id_empresa_usada = %s", (id_empresa,))
            cur.execute("DELETE FROM usuarios WHERE id_empresa = %s", (id_empresa,))
            cur.execute("DELETE FROM empresa_planos WHERE id_empresa = %s", (id_empresa,))
            cur.execute("DELETE FROM empresas WHERE id_empresa = %s", (id_empresa,))
            conn.commit()
    flash("Empresa e dados associados removidos com sucesso.", "success")
    return redirect(url_for('empresas.lista_convites'))



@empresas_bp.route("/solicitar-upgrade", methods=["POST"])
@login_required
def solicitar_upgrade():
    plano = request.form.get("plano") # "medio" ou "premium"
    
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO solicitacoes_upgrade (id_empresa, plano_desejado) VALUES (%s, %s)",
                (current_user.id_empresa, plano)
            )
            
    flash(f"Solicitação para o plano {plano.upper()} enviada com sucesso! Entraremos em contato.", "success")
    return redirect(url_for("main.dashboard"))



