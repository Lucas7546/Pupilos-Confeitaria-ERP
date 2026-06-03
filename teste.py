from dotenv import load_dotenv
from modules.db import get_conn

load_dotenv()




with get_conn() as conn:
    with conn.cursor() as cur:

        cur.execute("""
            SELECT
                id_produto,
                nome
            FROM produtos
        """)

        for linha in cur.fetchall():
            print(linha)

{{ EMPRESA }}