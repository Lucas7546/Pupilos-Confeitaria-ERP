from modules.db import get_conn


def criar_empresa(
    nome,
    responsavel,
    plano="basic"
):

    with get_conn() as conn:
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

        conn.commit()

    return id_empresa
