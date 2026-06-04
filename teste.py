from dotenv import load_dotenv
from modules.db import get_conn

load_dotenv()

with get_conn() as conn:
    with conn.cursor() as cur:

        cur.execute("""
            SELECT
                table_name,
                column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)

        atual = ""

        for tabela, coluna in cur.fetchall():

            if tabela != atual:
                print(f"\n[{tabela}]")
                atual = tabela

            print(" -", coluna)