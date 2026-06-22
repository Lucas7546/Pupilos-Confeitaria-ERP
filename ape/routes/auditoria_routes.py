from flask import Blueprint, render_template, request, Response, flash, redirect, url_for, session
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from modules.decorators import superadmin_required
from ape.services.log_service import registrar_log
from psycopg2.extras import DictCursor
import json
import secrets
from modules.admin_db import admin_conn
from modules.tenant_db import db_conn, db_admin_conn
from utils.logger import log_erro
from modules.termos import TEXTO_TERMOS, TERMOS_VERSAO
from datetime import datetime, timezone

auditoria_bp = Blueprint('auditoria', __name__)


# Helper interno - pode ficar aqui ou ser movido para app/services/log_service.py
def _listar_logs(
    limite=100,
    usuario=None,
    acao=None,
    modulo=None,
    data_inicio=None,
    data_fim=None
) -> list:

    try:

        id_empresa = getattr(current_user, "id_empresa", None)

        if not id_empresa:
            return []

        query = """
            SELECT
                usuario,
                acao,
                modulo,
                detalhe,
                data
            FROM logs
            WHERE id_empresa = %s
        """

        params = [id_empresa]

        if usuario:
            query += " AND LOWER(usuario) LIKE LOWER(%s)"
            params.append(f"%{usuario}%")

        if acao:
            query += " AND acao = %s"
            params.append(acao)

        if modulo:
            query += " AND modulo = %s"
            params.append(modulo)

        if data_inicio:
            query += " AND DATE(data) >= %s"
            params.append(data_inicio)

        if data_fim:
            query += " AND DATE(data) <= %s"
            params.append(data_fim)

        query += " ORDER BY data DESC LIMIT %s"
        params.append(limite)

        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()

    except Exception as e:
        log_erro(f"Erro ao consultar logs: {e}")
        return []


@auditoria_bp.route('/aceitar-termos', methods=['GET', 'POST'])
@login_required
def aceitar_termos():
    if request.method == 'POST':
        try:
            data_aceite = datetime.now(timezone.utc)
            ip_usuario = request.remote_addr

            with db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE empresas 
                        SET termos_aceitos = TRUE, 
                            data_aceite_termos = %s, 
                            versao_termos = %s 
                        WHERE id_empresa = %s
                    """, (
                        data_aceite,
                        TERMOS_VERSAO,
                        current_user.id_empresa
                    ))

            session.pop("plano", None)
            session.modified = True

            registrar_log(
                current_user.id_empresa,
                "TERMOS_ACEITE",
                f"Aceite realizado | Versão: {TERMOS_VERSAO} | IP: {ip_usuario}"
            )

            flash("Termos aceitos com sucesso.", "success")

            return redirect(url_for('main.dashboard'))

        except Exception as e:
            print(f"Erro ao aceitar termos: {e}")
            flash("Erro ao processar aceite dos termos.", "danger")

    return render_template(
        'aceitar_termos.html',
        termo=TEXTO_TERMOS,
        versao=TERMOS_VERSAO
    )

@auditoria_bp.route("/acessos")
@login_required
@superadmin_required
def listar_acessos():
    try:
        with admin_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        usuario,
                        empresa_nome,
                        ip,
                        tipo_evento,
                        data_evento
                    FROM acessos_sistema
                    ORDER BY data_evento DESC
                    LIMIT 500
                """)

                acessos = cur.fetchall()

        return render_template(
            "acessos.html",
            acessos=acessos
        )

    except Exception as e:
        log_erro(f"Erro listar acessos: {e}")
        flash("Erro ao carregar acessos.", "danger")
        return redirect(url_for("main.dashboard"))

@auditoria_bp.route("/auditoria")
@login_required
@acesso_requerido("auditoria")
def auditoria():

    try:

        usuario_f = request.args.get("usuario", "").strip()
        acao_f = request.args.get("acao", "").strip()
        modulo_f = request.args.get("modulo", "").strip()
        data_ini = request.args.get("data_inicio", "").strip()
        data_fim = request.args.get("data_fim", "").strip()

        try:
            limite = int(request.args.get("limite", 100))
            limite = max(1, min(limite, 1000))
        except (ValueError, TypeError):
            limite = 100

        logs_data = _listar_logs(
            limite,
            usuario_f,
            acao_f,
            modulo_f,
            data_ini,
            data_fim
        ) or []

        return render_template(
            "auditoria.html",
            logs=logs_data,
            usuario_filtro=usuario_f,
            acao_filtro=acao_f,
            modulo_filtro=modulo_f,
            data_inicio=data_ini,
            data_fim=data_fim,
            limite=limite,
        )

    except Exception as e:

        log_erro(f"Erro auditoria: {e}")

        return render_template(
            "auditoria.html",
            logs=[],
            limite=100
        )
@auditoria_bp.route("/logs/exportar")
@login_required
@superadmin_required
def exportar_logs():

    try:

        logs_brutos = _listar_logs(limite=1000) or []

        logs_fmt = []

        for log in logs_brutos:

            try:
                u, a, m, d, dt = log[:5]

                logs_fmt.append({
                    "usuario": u,
                    "acao": a,
                    "modulo": m,
                    "detalhe": d,
                    "data": str(dt)
                })

            except Exception:
                continue

        registrar_log(
            "EXPORT_LOGS",
            "AUDITORIA",
            "Backup exportado via JSON"
        )

        return Response(
            json.dumps(logs_fmt, indent=4, ensure_ascii=False),
            mimetype="application/json",
            headers={
                "Content-Disposition": "attachment; filename=auditoria.json"
            },
        )

    except Exception as e:

        log_erro(f"Erro exportar logs: {e}")

        return Response(
            json.dumps({"erro": "falha exportação"}),
            mimetype="application/json",
            status=500
        )


@auditoria_bp.route("/logs/limpar", methods=["POST"])
@login_required
@superadmin_required
def limpar_logs():

    try:

        id_empresa = getattr(current_user, "id_empresa", None)

        if not id_empresa:
            flash("Empresa inválida.", "danger")
            return redirect(url_for("auditoria.auditoria"))

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM logs
                    WHERE id_empresa = %s
                    """,
                    (id_empresa,)
                )

        registrar_log(
            "DELETE",
            "AUDITORIA",
            f"Logs apagados por {current_user.username}"
        )

        flash("Logs limpos com sucesso.", "success")

    except Exception as e:

        log_erro(f"Erro limpar logs: {e}")
        flash("Erro ao limpar logs.", "danger")

    return redirect(url_for("auditoria.auditoria"))

def gerar_codigo_convite() -> str:
    return secrets.token_hex(6).upper()


@auditoria_bp.route("/admin/convite/gerar", methods=["POST"])
@login_required
@superadmin_required
def gerar_convite():

    try:

        codigo = gerar_codigo_convite()

        with admin_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO convites_empresa
                    (
                        codigo,
                        plano,
                        criado_por
                    )
                    VALUES
                    (%s, %s, %s)
                """, (
                    codigo,
                    "starter",
                    current_user.id
                ))

        registrar_log(
            "CREATE",
            "CONVITE",
            f"Convite gerado: {codigo}"
        )

        flash(f"Convite criado: {codigo}", "success")

    except Exception as e:

        log_erro(f"Erro gerar_convite: {e}")
        flash("Erro ao gerar convite.", "danger")

    return redirect(url_for("empresas.lista_convites"))



@auditoria_bp.route("/admin/solicitacoes")
@login_required
@superadmin_required
def listar_solicitacoes():

    with db_admin_conn() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:

            # ======================
            # SOLICITAÇÕES
            # ======================

            cur.execute("""
                SELECT
                    s.*,
                    e.nome AS nome_empresa
                FROM solicitacoes_upgrade s
                LEFT JOIN empresas e
                    ON e.id_empresa = s.id_empresa
                WHERE s.status = 'pendente'
                ORDER BY s.data_criacao DESC
            """)

            pendentes = cur.fetchall()

            # ======================
            # FEEDBACKS
            # ======================

            cur.execute("""
                SELECT
                    f.*,
                    e.nome AS nome_empresa
                FROM feedback f
                LEFT JOIN empresas e
                    ON e.id_empresa = f.id_empresa
                ORDER BY f.data_criacao DESC
            """)

            feedbacks = cur.fetchall()

            # ======================
            # EMPRESAS
            # ======================

            cur.execute("""
                SELECT
                    e.id_empresa,
                    e.nome,
                    e.plano,

                    (
                        SELECT u.username
                        FROM usuarios u
                        WHERE u.id_empresa = e.id_empresa
                        AND u.nivel = 'admin'
                        LIMIT 1
                    ) AS responsavel

                FROM empresas e
                ORDER BY e.id_empresa
            """)

            empresas = cur.fetchall()

            print("FEEDBACKS:", len(feedbacks))
            print("EMPRESAS:", len(empresas))

    return render_template(
        "admin_solicitacoes.html",
        pendentes=pendentes,
        feedbacks=feedbacks,
        empresas=empresas
    )


@auditoria_bp.route("/admin/aprovar-upgrade/<uuid:id_solicitacao>", methods=["POST"])
@superadmin_required
def aprovar_upgrade(id_solicitacao):
    try:
        with db_admin_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # 1. Busca
                cur.execute("SELECT id_empresa, plano_desejado FROM solicitacoes_upgrade WHERE id_solicitacao = %s", (str(id_solicitacao),))
                solicitacao = cur.fetchone()
                
                if not solicitacao:
                    flash("Solicitação não encontrada.", "danger")
                    return redirect(url_for("auditoria.listar_solicitacoes"))

                id_empresa = solicitacao['id_empresa']
                novo_plano = solicitacao['plano_desejado']
                
                # 2. Executa as atualizações
                cur.execute("UPDATE empresas SET plano = %s WHERE id_empresa = %s", (novo_plano, id_empresa))
                cur.execute("UPDATE solicitacoes_upgrade SET status = 'aprovado' WHERE id_solicitacao = %s", (str(id_solicitacao),))
                
                # O bloco 'with conn' faz o commit automático ao final
                flash(f"Plano atualizado para {novo_plano.upper()} com sucesso!", "success")
    except Exception as e:
        print(f"Erro crítico na aprovação: {e}")
        flash("Erro ao processar a aprovação. Verifique o banco de dados.", "danger")
                
    return redirect(url_for("auditoria.listar_solicitacoes"))
