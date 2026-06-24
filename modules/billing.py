from modules.tenant_db import db_admin_conn
import traceback


def verificar_atrasos():
    """
    Atualiza status de assinatura em massa.
    """
    try:
        with db_admin_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE empresa_planos
                    SET 
                        dias_atraso = GREATEST(0, CURRENT_DATE - data_vencimento),

                        status_assinatura = CASE 
                            WHEN CURRENT_DATE > data_vencimento THEN 'overdue'
                            ELSE 'active'
                        END,

                        bloqueado = CASE
                            WHEN (CURRENT_DATE - data_vencimento) >= 5 THEN TRUE
                            ELSE FALSE
                        END

                    WHERE status_assinatura != 'cancelled'
                    AND data_vencimento IS NOT NULL
                """)

            conn.commit()

        print("Verificação de atrasos executada com sucesso.")

    except Exception:
        erro = traceback.format_exc()
        print(f"Erro em verificar_atrasos:\n{erro}")