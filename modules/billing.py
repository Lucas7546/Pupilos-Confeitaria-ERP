from modules.tenant_db import db_admin_conn
import traceback

def verificar_atrasos():
    """
    Executa a atualização em massa. 
    O banco processa tudo em milissegundos.
    """
    try:
        with db_admin_conn() as conn:
            with conn.cursor() as cur:
                # 1. Executa a atualização em massa
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
                
                # 2. Opcional: Registra que a rotina rodou com sucesso
                cur.execute("""
                    INSERT INTO logs_auditoria (acao, detalhe, created_at)
                    VALUES ('CRON_VERIFICACAO_ATRASOS', 'Rotina executada com sucesso via SQL', NOW())
                """)
                
                conn.commit()
                
        print(f"Verificação massiva concluída com sucesso.")

    except Exception as e:
        erro_detalhado = traceback.format_exc()
        print(f"Erro crítico na verificação de atrasos: {erro_detalhado}")
        traceback.print_exc()