from modules.tenant_db import db_conn


def criar_empresa(nome, responsavel, plano="basic", cursor=None):
    try:
        # Se um cursor foi passado, usamos ele para manter a transação
        if cursor:
            cursor.execute("""
                INSERT INTO empresas (nome, responsavel, plano)
                VALUES (%s, %s, %s)
                RETURNING id_empresa
            """, (nome, responsavel, plano))

            id_empresa = cursor.fetchone()[0]

            # O (1)::boolean resolve o conflito entre inteiro e booleano
            cursor.execute("""
                INSERT INTO empresa_planos (id_empresa, plano, ativo)
                VALUES (%s, %s, (1)::boolean)
            """, (id_empresa, plano))

            return id_empresa

        # Caso contrário, abrimos uma nova conexão
        else:
            with db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO empresas (nome, responsavel, plano)
                        VALUES (%s, %s, %s)
                        RETURNING id_empresa
                    """, (nome, responsavel, plano))

                    id_empresa = cur.fetchone()[0]

                    cur.execute("""
                        INSERT INTO empresa_planos (id_empresa, plano, ativo)
                        VALUES (%s, %s, (1)::boolean)
                    """, (id_empresa, plano))

                    conn.commit()
                    return id_empresa

    except Exception as e:
        raise Exception(f"Erro ao criar empresa: {e}")

def buscar_empresa_nome(nome):

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