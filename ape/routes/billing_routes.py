from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from modules.tenant_db import db_admin_conn, current_user
import os
import mercadopago
import traceback

billing_bp = Blueprint("billing", __name__)

# Configura o SDK
token = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")
if not token:
    raise ValueError("MERCADO_PAGO_ACCESS_TOKEN não configurado no ambiente!")
sdk = mercadopago.SDK(token)

@billing_bp.route("/billing/gerar-pix-atraso")
@login_required
def gerar_pix_atraso():
    try:
        with db_admin_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT valor_plano FROM empresa_planos WHERE id_empresa = %s", (current_user.id_empresa,))
                res = cur.fetchone()
                valor_a_pagar = float(res[0]) if res else 200.00
        
        request_payment = {
            "transaction_amount": valor_a_pagar,
            "description": f"Assinatura - Empresa {current_user.id_empresa}",
            "payment_method_id": "pix",
            "external_reference": str(current_user.id_empresa),
            "payer": {"email": current_user.email}
        }

        result = sdk.payment().create(request_payment)
        payment = result.get("response")
        
        if not payment or "point_of_interaction" not in payment:
            return "Erro ao comunicar com Mercado Pago", 500

        return render_template("pagar_atraso.html", 
                               pix_code=payment["point_of_interaction"]["transaction_data"]["qr_code"], 
                               qr_code_base64=payment["point_of_interaction"]["transaction_data"]["qr_code_base64"],
                               valor=valor_a_pagar)

    except Exception:
        erro_detalhado = traceback.format_exc()
        print(f"Erro crítico em gerar pix: {erro_detalhado}")
        traceback.print_exc()
        return "Erro interno ao processar pagamento", 500

@billing_bp.route("/billing/webhook", methods=["POST"])
def webhook():
    # 1. Verifica se a requisição tem o tipo de evento esperado
    data = request.get_json()
    if not data or data.get("type") != "payment":
        return jsonify({"status": "ignored"}), 200

    payment_id = data.get("data", {}).get("id")
    
    try:
        # 2. CONSULTA O MERCADO PAGO DIRETAMENTE (BLINDAGEM)
        # NUNCA confie nos dados que chegam no POST, sempre peça confirmação à API
        payment_info = sdk.payment().get(payment_id, request_options=None)
        payment_data = payment_info.get("response")
        
        status = payment_data.get("status")
        id_empresa = payment_data.get("external_reference")

        # 3. Processa apenas se o pagamento estiver aprovado
        if status == "approved":
            with db_admin_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE empresa_planos
                        SET status_assinatura = 'active',
                            dias_atraso = 0,
                            bloqueado = FALSE,
                            ultimo_pagamento = NOW()
                        WHERE id_empresa = %s
                    """, (id_empresa,))
            print(f"Pagamento {payment_id} validado e processado para empresa {id_empresa}")
            
        return jsonify({"status": "success"}), 200

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        print(f"Erro crítico no Webhook: {erro_detalhado}")
        traceback.print_exc()
        return jsonify({"status": "error"}), 500


@billing_bp.route("/conta-bloqueada")
def conta_bloqueada():
    return render_template("conta_bloqueada.html")


