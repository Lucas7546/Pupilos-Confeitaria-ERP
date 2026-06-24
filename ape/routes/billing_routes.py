from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from modules.tenant_db import db_admin_conn
import os
import mercadopago
import traceback
import unicodedata
import re

billing_bp = Blueprint("billing", __name__)

token = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")
if not token:
    raise ValueError("MERCADO_PAGO_ACCESS_TOKEN não configurado!")

sdk = mercadopago.SDK(token)


# =========================
# UTIL
# =========================
def limpar_nome(nome):
    nome = unicodedata.normalize("NFKD", nome)
    nome = nome.encode("ASCII", "ignore").decode("ASCII")
    nome = re.sub(r"[^a-zA-Z0-9]", "", nome)
    return nome.lower()


def gerar_email_pagador():
    nome = getattr(current_user, 'nome_empresa', None)

    if not nome:
        nome = "empresa"

    nome_limpo = limpar_nome(nome)

    return f"{current_user.id_empresa}{nome_limpo}@lumenarch.com.br"


def obter_valor_plano(plano):
    if plano == "starter":
        return 180.00
    elif plano == "enterprise":
        return 300.00
    return 200.00


# =========================
# CONTA BLOQUEADA
# =========================
@billing_bp.route("/conta-bloqueada")
@login_required
def conta_bloqueada():
    with db_admin_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dias_atraso
                FROM empresa_planos
                WHERE id_empresa = %s
            """, (current_user.id_empresa,))
            res = cur.fetchone()

    dias_atraso = res[0] if res else 0

    return render_template(
        "conta_bloqueada.html",
        dias_atraso=dias_atraso
    )


# =========================
# PIX ATRASO
# =========================
@billing_bp.route("/billing/gerar-pix-atraso")
@login_required
def gerar_pix_atraso():
    try:
        with db_admin_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT plano
                    FROM empresa_planos
                    WHERE id_empresa = %s
                """, (current_user.id_empresa,))
                res = cur.fetchone()

        plano = res[0] if res else "starter"
        valor_a_pagar = obter_valor_plano(plano)

        request_payment = {
            "transaction_amount": valor_a_pagar,
            "description": f"Pagamento em atraso - Empresa {current_user.id_empresa}",
            "payment_method_id": "pix",
            "external_reference": f"atraso_{current_user.id_empresa}",
            "payer": {
                "email": gerar_email_pagador()
            }
        }

        result = sdk.payment().create(request_payment)
        payment = result.get("response")

        if not payment or "point_of_interaction" not in payment:
            return "Erro Mercado Pago", 500

        payment_id = str(payment["id"])
        qr_code = payment["point_of_interaction"]["transaction_data"]["qr_code"]
        qr_code_base64 = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]

        with db_admin_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pagamentos (
                        id_empresa,
                        payment_id,
                        tipo,
                        valor,
                        status,
                        qr_code,
                        qr_code_base64
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                    current_user.id_empresa,
                    payment_id,
                    "atraso",
                    valor_a_pagar,
                    "pending",
                    qr_code,
                    qr_code_base64
                ))

        return render_template(
            "pagar_atraso.html",
            pix_code=qr_code,
            qr_code_base64=qr_code_base64,
            valor=valor_a_pagar
        )

    except Exception:
        print(traceback.format_exc())
        return "Erro interno", 500


# =========================
# PIX MENSALIDADE
# =========================
@billing_bp.route("/billing/gerar-pix-atual")
@login_required
def gerar_pix_atual():
    try:
        with db_admin_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT plano
                    FROM empresa_planos
                    WHERE id_empresa = %s
                """, (current_user.id_empresa,))
                res = cur.fetchone()

        plano = res[0] if res else "starter"
        valor_a_pagar = obter_valor_plano(plano)

        request_payment = {
            "transaction_amount": valor_a_pagar,
            "description": f"Mensalidade - Empresa {current_user.id_empresa}",
            "payment_method_id": "pix",
            "external_reference": f"mensalidade_{current_user.id_empresa}",
            "payer": {
                "email": gerar_email_pagador()
            }
        }

        result = sdk.payment().create(request_payment)
        payment = result.get("response")

        if not payment or "point_of_interaction" not in payment:
            return "Erro Mercado Pago", 500

        payment_id = str(payment["id"])
        qr_code = payment["point_of_interaction"]["transaction_data"]["qr_code"]
        qr_code_base64 = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]

        with db_admin_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pagamentos (
                        id_empresa,
                        payment_id,
                        tipo,
                        valor,
                        status,
                        qr_code,
                        qr_code_base64
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                    current_user.id_empresa,
                    payment_id,
                    "mensalidade",
                    valor_a_pagar,
                    "pending",
                    qr_code,
                    qr_code_base64
                ))

        return render_template(
            "pagar_pix.html",
            pix_code=qr_code,
            qr_code_base64=qr_code_base64,
            valor=valor_a_pagar
        )

    except Exception:
        print(traceback.format_exc())
        return "Erro interno", 500


# =========================
# WEBHOOK
# =========================
@billing_bp.route("/billing/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if not data or data.get("type") != "payment":
        return jsonify({"status": "ignored"}), 200

    payment_id = data.get("data", {}).get("id")

    try:
        payment_info = sdk.payment().get(payment_id)
        payment_data = payment_info.get("response")

        status = payment_data.get("status")
        external_reference = payment_data.get("external_reference")

        if not external_reference:
            return jsonify({"status": "no external reference"}), 400

        partes = external_reference.split("_")

        if len(partes) != 2:
            return jsonify({"status": "invalid reference"}), 400

        tipo = partes[0]
        id_empresa = int(partes[1])

        if status == "approved":
            with db_admin_conn() as conn:
                with conn.cursor() as cur:

                    cur.execute("""
                        UPDATE pagamentos
                        SET status = 'approved',
                            paid_at = NOW()
                        WHERE payment_id = %s
                    """, (str(payment_id),))

                    cur.execute("""
                        UPDATE empresa_planos
                        SET
                            status_assinatura = 'active',
                            dias_atraso = 0,
                            bloqueado = FALSE,
                            ultimo_pagamento = NOW(),
                            data_vencimento = CURRENT_DATE + INTERVAL '30 days'
                        WHERE id_empresa = %s
                    """, (id_empresa,))

            print(
                f"Pagamento aprovado | Empresa={id_empresa} | Tipo={tipo}"
            )

        return jsonify({"status": "success"}), 200

    except Exception:
        print(traceback.format_exc())
        return jsonify({"status": "error"}), 500