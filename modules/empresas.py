from modules.db import get_conn

def criar_empresa(nome, plano="basic"):

    with get_conn() as conn:
        with conn.cursor() as cur:

            # 1. cria empresa
            cur.execute("""
                INSERT INTO empresas (nome, plano)
                VALUES (%s, %s)
                RETURNING id_empresa
            """, (nome, plano))

            id_empresa = cur.fetchone()[0]

            # 2. cria plano ativo (controle SaaS)
            cur.execute("""
                INSERT INTO empresa_planos (id_empresa, plano, ativo)
                VALUES (%s, %s, TRUE)
            """, (id_empresa, plano))

        conn.commit()
