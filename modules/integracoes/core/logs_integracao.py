from modules.tenant_db import db_conn
from utils.logger import log_erro
from psycopg2.extras import Json, DictCursor
import traceback


def registrar_log_integracao(
    id_empresa,
    provider,
    tipo,
    mensagem,
    payload=None,
    order_id=None
):

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO integracao_logs
                    (
                        id_empresa,
                        provider,
                        tipo,
                        mensagem,
                        payload,
                        order_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    id_empresa,
                    provider,
                    tipo,
                    mensagem,
                    Json(payload) if payload else None,
                    order_id
                ))

        return True

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

        return False


def buscar_logs_integracao(id_empresa, provider=None, limite=100):

    try:
        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                if provider:
                    cur.execute("""
                        SELECT *
                        FROM integracao_logs
                        WHERE id_empresa = %s
                        AND provider = %s
                        ORDER BY data_evento DESC
                        LIMIT %s
                    """, (
                        id_empresa,
                        provider,
                        limite
                    ))
                else:
                    cur.execute("""
                        SELECT *
                        FROM integracao_logs
                        WHERE id_empresa = %s
                        ORDER BY data_evento DESC
                        LIMIT %s
                    """, (
                        id_empresa,
                        limite
                    ))

                logs = cur.fetchall()

                return logs

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