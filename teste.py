from dotenv import load_dotenv
from modules.db import get_conn

load_dotenv()


with get_conn() as conn:
    with conn.cursor() as cur:

        cur.execute("""
        SELECT
            column_name
        FROM information_schema.columns
        WHERE table_name = 'movimentacao_produtos'
        ORDER BY ordinal_position
        """)

        for c in cur.fetchall():
            print(c[0])