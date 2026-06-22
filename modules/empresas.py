import traceback
from modules.tenant_db import db_conn
from utils.logger import log_erro
from modules.termos import TERMOS_VERSAO


def criar_empresa(nome, responsavel, plano="starter", cursor=None):
    try:
        sql_insert_empresa = """
            INSERT INTO empresas (
                nome,
                responsavel,
                plano,
                termos_aceitos,
                data_aceite_termos,
                versao_termos
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_empresa
        """

        params_empresa = (
            nome,
            responsavel,
            plano,
            False,
            None,
            TERMOS_VERSAO
        )

        sql_insert_plano = """
            INSERT INTO empresa_planos (id_empresa, plano, ativo)
            VALUES (%s, %s, 1)
        """

        if cursor:
            cursor.execute(sql_insert_empresa, params_empresa)
            row = cursor.fetchone()

            if not row:
                raise Exception("Falha ao retornar id_empresa")

            id_empresa = row[0]

            cursor.execute(sql_insert_plano, (id_empresa, plano))
            return id_empresa

        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_insert_empresa, params_empresa)
                row = cur.fetchone()

                if not row:
                    raise Exception("Falha ao retornar id_empresa")

                id_empresa = row[0]

                cur.execute(sql_insert_plano, (id_empresa, plano))

                conn.commit()
                return id_empresa

    except Exception as e:
        erro_trace = traceback.format_exc()

        log_erro(
            "Erro ao criar empresa",
            extra={
                "nome": nome,
                "responsavel": responsavel,
                "plano": plano,
                "erro": str(e),
                "traceback": erro_trace
            }
        )

        raise


def buscar_empresa_nome(nome):
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_empresa
                    FROM empresas
                    WHERE LOWER(nome) = LOWER(%s)
                    LIMIT 1
                    """,
                    (nome,)
                )

                return cur.fetchone()

    except Exception as e:
        erro_trace = traceback.format_exc()

        log_erro(
            "Erro ao buscar empresa por nome",
            extra={
                "nome": nome,
                "erro": str(e),
                "traceback": erro_trace
            }
        )

        raise