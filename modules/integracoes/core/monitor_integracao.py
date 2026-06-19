from modules.tenant_db import db_conn
from psycopg2.extras import DictCursor
from utils.logger import log_erro
import traceback


def buscar_metricas_monitoramento(id_empresa, provider=None):

    try:

        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                if provider:
                    cur.execute("""
                        SELECT
                            COUNT(*) as total_pedidos,

                            COUNT(*) FILTER (
                                WHERE status = 'processado'
                            ) as processados,

                            COUNT(*) FILTER (
                                WHERE status = 'pendente'
                            ) as pendentes,

                            COUNT(*) FILTER (
                                WHERE status = 'erro'
                            ) as erros

                        FROM integracao_pedidos
                        WHERE id_empresa = %s
                        AND provider = %s
                    """, (
                        id_empresa,
                        provider
                    ))
                else:
                    cur.execute("""
                        SELECT
                            COUNT(*) as total_pedidos,

                            COUNT(*) FILTER (
                                WHERE status = 'processado'
                            ) as processados,

                            COUNT(*) FILTER (
                                WHERE status = 'pendente'
                            ) as pendentes,

                            COUNT(*) FILTER (
                                WHERE status = 'erro'
                            ) as erros

                        FROM integracao_pedidos
                        WHERE id_empresa = %s
                    """, (id_empresa,))

                return cur.fetchone()

    except Exception as e:

        erro_detalhado = traceback.format_exc()

        log_erro(f"""
Erro: {str(e)}

Traceback:
{erro_detalhado}
""")

        traceback.print_exc()

        return None
    

def listar_falhas_integracao(id_empresa, provider=None):

    try:

        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                if provider:
                    cur.execute("""
                        SELECT
                            provider,
                            order_id,
                            status,
                            erro,
                            tentativas,
                            data_processamento
                        FROM integracao_pedidos
                        WHERE id_empresa = %s
                        AND provider = %s
                        AND status = 'erro'
                        ORDER BY data_processamento DESC
                    """, (
                        id_empresa,
                        provider
                    ))
                else:
                    cur.execute("""
                        SELECT
                            provider,
                            order_id,
                            status,
                            erro,
                            tentativas,
                            data_processamento
                        FROM integracao_pedidos
                        WHERE id_empresa = %s
                        AND status = 'erro'
                        ORDER BY data_processamento DESC
                    """, (id_empresa,))

                return cur.fetchall()

    except Exception as e:

        erro_detalhado = traceback.format_exc()

        log_erro(f"""
Erro: {str(e)}

Traceback:
{erro_detalhado}
""")

        traceback.print_exc()

        return []

def listar_integracoes_ativas(id_empresa):

    try:

        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                cur.execute("""
                    SELECT
                        provider,
                        merchant_id,
                        ativo
                    FROM integracoes
                    WHERE id_empresa = %s
                    AND ativo = TRUE
                """, (id_empresa,))

                return cur.fetchall()

    except Exception as e:

        erro_detalhado = traceback.format_exc()

        log_erro(f"""
Erro: {str(e)}

Traceback:
{erro_detalhado}
""")

        traceback.print_exc()

        return []
    
def buscar_logs_integracao(id_empresa, provider=None):

    try:

        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                if provider:
                    cur.execute("""
                        SELECT
                            provider,
                            tipo,
                            mensagem,
                            order_id,
                            data_evento
                        FROM integracao_logs
                        WHERE id_empresa = %s
                        AND provider = %s
                        ORDER BY data_evento DESC
                        LIMIT 100
                    """, (
                        id_empresa,
                        provider
                    ))
                else:
                    cur.execute("""
                        SELECT
                            provider,
                            tipo,
                            mensagem,
                            order_id,
                            data_evento
                        FROM integracao_logs
                        WHERE id_empresa = %s
                        ORDER BY data_evento DESC
                        LIMIT 100
                    """, (id_empresa,))

                return cur.fetchall()

    except Exception as e:

        erro_detalhado = traceback.format_exc()

        log_erro(f"""
Erro: {str(e)}

Traceback:
{erro_detalhado}
""")

        traceback.print_exc()

        return []
    


def listar_monitoramento(id_empresa, limite=50, provider=None):

    try:

        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:

                if provider:
                    cur.execute("""
                        SELECT
                            provider,
                            order_id,
                            status,
                            tentativas,
                            erro,
                            data_recebimento,
                            data_processamento
                        FROM integracao_pedidos
                        WHERE id_empresa = %s
                        AND provider = %s
                        ORDER BY data_recebimento DESC
                        LIMIT %s
                    """, (
                        id_empresa,
                        provider,
                        limite
                    ))
                else:
                    cur.execute("""
                        SELECT
                            provider,
                            order_id,
                            status,
                            tentativas,
                            erro,
                            data_recebimento,
                            data_processamento
                        FROM integracao_pedidos
                        WHERE id_empresa = %s
                        ORDER BY data_recebimento DESC
                        LIMIT %s
                    """, (
                        id_empresa,
                        limite
                    ))

                return cur.fetchall()

    except Exception as e:

        erro_detalhado = traceback.format_exc()

        log_erro(f"""
Erro: {str(e)}

Traceback:
{erro_detalhado}
""")

        traceback.print_exc()

        return []