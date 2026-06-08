from modules.db import get_conn


def criar_empresa(
    nome,
    responsavel,
    plano="basic",
    conn=None
):
    with conn.cursor() as cur:

        cur.execute("""
            INSERT INTO empresas
            (
                nome,
                responsavel,
                plano
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            RETURNING id_empresa
        """,
        (
            nome,
            responsavel,
            plano
        ))

        id_empresa = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO empresa_planos
            (
                id_empresa,
                plano,
                ativo
            )
            VALUES
            (
                %s,
                %s,
                TRUE
            )
        """,
        (
            id_empresa,
            plano
        ))

        cur.execute("""
            INSERT INTO empresa_config
            (
                id_empresa,
                regime_fiscal
            )
            VALUES
            (
                %s,
                'Simples Nacional'
            )
        """,
        (
            id_empresa,
        ))

        return id_empresa


def buscar_empresa_nome(nome):

    with get_conn() as conn:
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