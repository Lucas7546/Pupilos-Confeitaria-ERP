from modules.tenant_db import db_conn
from utils.logger import log_erro
from psycopg2.extras import Json, DictCursor
import traceback

def salvar_pedido_integracao(id_empresa, provider, order_id, payload):
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO integracao_pedidos
                    (id_empresa, provider, order_id, payload, status)
                    VALUES (%s, %s, %s, %s, 'pendente')
                    ON CONFLICT (id_empresa, provider, order_id)
                    DO UPDATE SET payload = EXCLUDED.payload
                    RETURNING id
                """, (id_empresa, provider, order_id, Json(payload)))
                resultado = cur.fetchone()
        return resultado[0]
    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao salvar pedido {order_id}: {str(e)}\nTraceback: {erro_detalhado}")
        traceback.print_exc()
        return None

def salvar_evento_integracao(id_empresa, provider, event_type, order_id, payload):
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO integracao_eventos
                    (id_empresa, provider, event_type, order_id, payload)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id_empresa, provider, event_type, order_id, Json(payload)))
        return True
    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao salvar evento {order_id}: {str(e)}\nTraceback: {erro_detalhado}")
        traceback.print_exc()
        return False

def buscar_pedido_integracao(id_empresa, provider, order_id):
    try:
        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT * FROM integracao_pedidos
                    WHERE id_empresa = %s AND provider = %s AND order_id = %s
                """, (id_empresa, provider, order_id))
                return cur.fetchone()
    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao buscar pedido {order_id}: {str(e)}\nTraceback: {erro_detalhado}")
        traceback.print_exc()
        return None

def marcar_pedido_processado(id_empresa, provider, order_id):
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE integracao_pedidos
                    SET status = 'processado', erro = NULL, data_processamento = NOW()
                    WHERE id_empresa = %s AND provider = %s AND order_id = %s
                """, (id_empresa, provider, order_id))
        return True
    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao processar pedido {order_id}: {str(e)}\nTraceback: {erro_detalhado}")
        traceback.print_exc()
        return False

def marcar_pedido_erro(id_empresa, provider, order_id, erro):
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE integracao_pedidos
                    SET status = 'erro', erro = %s
                    WHERE id_empresa = %s AND provider = %s AND order_id = %s
                """, (erro, id_empresa, provider, order_id))
        return True
    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao marcar erro no pedido {order_id}: {str(e)}\nTraceback: {erro_detalhado}")
        traceback.print_exc()
        return False

def incrementar_tentativa(id_empresa, provider, order_id):
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE integracao_pedidos
                    SET tentativas = tentativas + 1
                    WHERE id_empresa = %s AND provider = %s AND order_id = %s
                """, (id_empresa, provider, order_id))
        return True
    except Exception as e:
        erro_detalhado = traceback.format_exc()
        log_erro(f"Erro ao incrementar tentativa {order_id}: {str(e)}\nTraceback: {erro_detalhado}")
        traceback.print_exc()
        return False