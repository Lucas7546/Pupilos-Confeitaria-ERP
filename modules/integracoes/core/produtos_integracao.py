from modules.tenant_db import db_conn
from utils.logger import log_erro
import traceback


def buscar_mapeamento_produto(id_empresa, provider, id_produto_externo):

    try:

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        id_produto_interno,
                        id_produto_externo,
                        nome_externo
                    FROM integracao_produtos
                    WHERE id_empresa = %s
                    AND provider = %s
                    AND id_produto_externo = %s
                """, (
                    id_empresa,
                    provider,
                    str(id_produto_externo)
                ))

                produto = cur.fetchone()

                return produto

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

        return None


def salvar_mapeamento_produto(
    id_empresa,
    provider,
    id_produto_interno,
    id_produto_externo,
    nome_externo
):

    try:

        with db_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO integracao_produtos
                    (
                        id_empresa,
                        provider,
                        id_produto_interno,
                        id_produto_externo,
                        nome_externo
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id_empresa, provider, id_produto_externo)
                    DO UPDATE SET
                        id_produto_interno = EXCLUDED.id_produto_interno,
                        nome_externo = EXCLUDED.nome_externo
                """, (
                    id_empresa,
                    provider,
                    id_produto_interno,
                    str(id_produto_externo),
                    nome_externo
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