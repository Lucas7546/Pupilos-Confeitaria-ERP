from dotenv import load_dotenv
from modules.db import get_conn

load_dotenv()

with get_conn() as conn:
    with conn.cursor() as cur:

        cur.execute("""
            SELECT
                p.id_produto,
                p.nome,
                COALESCE(
                    SUM(
                        CASE
                            WHEN mov.tipo_movimento = 'entrada'
                            THEN mov.quantidade
                            ELSE 0
                        END
                    ),0
                ) AS fabricado,
                COALESCE(SUM(iv.quantidade),0) AS vendido

            FROM produtos p

            LEFT JOIN movimentacao_estoque mov
                ON mov.id_produto = p.id_produto

            LEFT JOIN itens_venda iv
                ON iv.id_produto = p.id_produto

            GROUP BY
                p.id_produto,
                p.nome

            ORDER BY
                p.nome
        """)

        for linha in cur.fetchall():
            print(linha)