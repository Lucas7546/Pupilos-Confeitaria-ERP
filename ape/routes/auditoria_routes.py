from flask import Blueprint, render_template, request, Response
from flask_login import login_required, current_user
from modules.permissoes import acesso_requerido
from ape.services.log_service import registrar_log
from modules.db import get_conn
from utils.logger import log_erro
import json

auditoria_bp = Blueprint('auditoria', __name__)

# Helper interno - pode ficar aqui ou ser movido para app/services/log_service.py
def _listar_logs(limite=100, usuario=None, acao=None, modulo=None, 
                  data_inicio=None, data_fim=None) -> list:
    query = "SELECT usuario, acao, modulo, detalhe, data FROM logs WHERE 1=1"
    params = []

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

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
    except Exception as e:
        log_erro(f"Erro ao consultar logs: {e}")
        return []

@auditoria_bp.route("/auditoria")
@login_required
@acesso_requerido("auditoria")
def auditoria():
    usuario_f = request.args.get("usuario", "").strip()
    acao_f = request.args.get("acao", "").strip()
    modulo_f = request.args.get("modulo", "").strip()
    data_ini = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()
    
    try:
        limite = max(1, min(int(request.args.get("limite", 100)), 1000))
    except (ValueError, TypeError):
        limite = 100

    logs_data = _listar_logs(limite, usuario_f, acao_f, modulo_f, data_ini, data_fim)
    
    return render_template(
        "auditoria.html",
        logs=logs_data,
        usuario_filtro=usuario_f, acao_filtro=acao_f, modulo_filtro=modulo_f,
        data_inicio=data_ini, data_fim=data_fim, limite=limite,
    )

@auditoria_bp.route("/logs/exportar")
@login_required
@acesso_requerido("auditoria")
def exportar_logs():
    logs_brutos = _listar_logs(limite=1000)
    logs_fmt = []
    for log in logs_brutos:
        try:
            u, a, m, d, dt = log[:5]
            logs_fmt.append({"usuario": u, "acao": a, "modulo": m, "detalhe": d, "data": str(dt)})
        except (IndexError, TypeError):
            continue

    registrar_log("EXPORT_LOGS", "AUDITORIA", "Backup exportado via JSON")
    return Response(
        json.dumps(logs_fmt, indent=4, ensure_ascii=False),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=auditoria_pupilos.json"},
    )
