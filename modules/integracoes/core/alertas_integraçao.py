from modules.tenant_db import db_conn
from utils.logger import log_erro
from psycopg2.extras import DictCursor
import traceback


def buscar_alertas_integracao(id_empresa):

    try:

        alertas = []

        alertas.extend(alerta_integracao_inativa(id_empresa))
        alertas.extend(alerta_pedidos_com_erro(id_empresa))
        alertas.extend(alerta_pedidos_pendentes(id_empresa))

        return alertas

    except Exception as e:

        erro_detalhado = traceback.format_exc()

        log_erro(
            f"""
Erro: {str(e)}

Traceback:
{erro_detalhado}
"""
        )

        traceback.print_exc()

        return []
    
def alerta_integracao_inativa(id_empresa):

    try:

        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                cur.execute("""
                    SELECT provider
                    FROM integracoes
                    WHERE id_empresa = %s
                    AND ativo = FALSE
                """, (id_empresa,))

                rows = cur.fetchall()

                alertas = []

                for row in rows:
                    alertas.append({
                        "tipo": "integracao_inativa",
                        "provider": row["provider"],
                        "mensagem": f"Integração {row['provider']} está inativa"
                    })

                return alertas

    except Exception as e:

        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro: {str(e)}\n{erro_detalhado}")
        traceback.print_exc()

        return []
    
def alerta_pedidos_com_erro(id_empresa):

    try:

        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                cur.execute("""
                    SELECT provider, COUNT(*) as total
                    FROM integracao_pedidos
                    WHERE id_empresa = %s
                    AND status = 'erro'
                    GROUP BY provider
                """, (id_empresa,))

                rows = cur.fetchall()

                alertas = []

                for row in rows:
                    if row["total"] > 0:
                        alertas.append({
                            "tipo": "pedido_com_erro",
                            "provider": row["provider"],
                            "mensagem": f"{row['total']} pedidos com erro em {row['provider']}"
                        })

                return alertas

    except Exception as e:

        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro: {str(e)}\n{erro_detalhado}")
        traceback.print_exc()

        return []
    
def alerta_pedidos_pendentes(id_empresa):

    try:

        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                cur.execute("""
                    SELECT provider, COUNT(*) as total
                    FROM integracao_pedidos
                    WHERE id_empresa = %s
                    AND status = 'pendente'
                    GROUP BY provider
                """, (id_empresa,))

                rows = cur.fetchall()

                alertas = []

                for row in rows:
                    if row["total"] > 0:
                        alertas.append({
                            "tipo": "pedido_pendente",
                            "provider": row["provider"],
                            "mensagem": f"{row['total']} pedidos pendentes em {row['provider']}"
                        })

                return alertas

    except Exception as e:

        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro: {str(e)}\n{erro_detalhado}")
        traceback.print_exc()

        return []
    