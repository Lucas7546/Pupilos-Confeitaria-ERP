from flask import Blueprint, request, flash, send_file, make_response, redirect, url_for
from flask_login import login_required, current_user

import io
import csv
import pandas as pd

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from modules.permissoes import acesso_requerido
from utils.logger import log_erro
from ape.services.log_service import registrar_log
from modules.estoque import previsao_demanda
from ape.extensions import limiter

export_bp = Blueprint("export", __name__)


# =====================================================
# CSV EXPORT
# =====================================================
@export_bp.route("/exportar-previsao/csv")
@login_required
@acesso_requerido("estoque")
@limiter.limit("10 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def exportar_previsao_csv():

    try:

        previsoes = previsao_demanda(current_user.id_empresa)

        if not previsoes:

            flash("Nenhum dado disponível.", "warning")
            return redirect(url_for("main.dashboard"))

        output = io.StringIO()
        output.write("\ufeff")

        writer = csv.writer(output, delimiter=";")

        header = [
            "Matéria-Prima",
            "Unidade",
            "Estoque Atual",
            "Consumo Diário",
            "Consumo 7 Dias",
            "Consumo 15 Dias",
            "Dias Restantes",
            "Risco",
            "Sugestão Compra"
        ]

        writer.writerow(header)

        for item in previsoes:

            writer.writerow([
                item.get("materia_prima", "N/A"),
                item.get("unidade", "UN"),

                round(float(item.get("estoque_atual") or 0), 2),
                round(float(item.get("media_diaria") or 0), 2),
                round(float(item.get("consumo_previsto") or 0), 2),
                round(float(item.get("consumo_15d") or 0), 2),
                round(float(item.get("dias_restantes") or 0), 2),

                item.get("risco", "BAIXO"),
                round(float(item.get("sugestao_compra") or 0), 2),
            ])

        registrar_log("EXPORT_CSV", "EXPORT", f"{len(previsoes)} itens exportados")

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=previsao.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8-sig"

        return response


    except Exception as e:

        log_erro(f"[CSV EXPORT ERROR] {e}")

        flash("Erro ao gerar CSV.", "danger")

        return redirect(url_for("main.dashboard"))


# =====================================================
# EXCEL EXPORT
# =====================================================
@export_bp.route("/exportar-previsao/excel")
@login_required
@acesso_requerido("estoque")
@limiter.limit("10 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def exportar_previsao_excel():

    try:

        previsoes = previsao_demanda(current_user.id_empresa)

        if not previsoes:

            flash("Dados indisponíveis.", "info")
            return redirect(url_for("main.dashboard"))

        df = pd.DataFrame(previsoes)

        df = df.rename(columns={
            "materia_prima": "Matéria-Prima",
            "unidade": "Unidade",
            "estoque_atual": "Estoque Atual",
            "media_diaria": "Consumo Diário",
            "consumo_previsto": "7 Dias",
            "consumo_15d": "15 Dias",
            "dias_restantes": "Autonomia",
            "risco": "Risco",
            "sugestao_compra": "Compra Sugerida",
        })

        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Previsao")

        buffer.seek(0)

        registrar_log("EXPORT_CSV", "EXPORT", f"{len(previsoes)} itens exportados")

        return send_file(
            buffer,
            download_name="previsao.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


    except Exception as e:

        log_erro(f"[EXCEL EXPORT ERROR] {e}")

        flash("Erro ao gerar Excel.", "danger")

        return redirect(url_for("main.dashboard"))


# =====================================================
# PDF EXPORT
# =====================================================
@export_bp.route("/exportar-previsao/pdf")
@login_required
@limiter.limit("10 per minute") # Limite do usuário
@limiter.limit("60 per hour", key_func=lambda: f"empresa:{current_user.id_empresa}") # Limite da empresa
def exportar_previsao_pdf():

    try:

        previsoes = previsao_demanda(current_user.id_empresa)

        if not previsoes:

            flash("Sem dados.", "info")
            return redirect(url_for("main.dashboard"))

        buffer = io.BytesIO()

        doc = SimpleDocTemplate(buffer, pagesize=letter)

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "title",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#1A237E")
        )

        elements = [
            Paragraph("Previsão de Estoque", title_style),
            Spacer(1, 12),
        ]

        data = [["Matéria", "Estoque", "Dias", "Risco", "Sugestão"]]

        for item in previsoes:

            data.append([
                item.get("materia_prima", "N/A"),
                round(float(item.get("estoque_atual") or 0), 2),
                round(float(item.get("dias_restantes") or 0), 2),
                item.get("risco", "BAIXO"),
                round(float(item.get("sugestao_compra") or 0), 2),
            ])

        table = Table(data)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A237E")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        elements.append(table)

        doc.build(elements)

        buffer.seek(0)

        registrar_log(
            usuario=current_user.id,
            acao="EXPORT_PDF",
            detalhes=f"{len(previsoes)} itens exportados"
        )

        return send_file(
            buffer,
            as_attachment=True,
            download_name="previsao.pdf"
        )


    except Exception as e:

        log_erro(f"[PDF EXPORT ERROR] {e}")

        flash("Erro ao gerar PDF.", "danger")

        return redirect(url_for("main.dashboard"))