from dotenv import load_dotenv
from modules.db import get_conn

load_dotenv()

with get_conn() as conn:
    with conn.cursor() as cur:

        cur.execute("""
            ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS id_empresa INT;
        """)

        conn.commit()

print("\nPROCESSO FINALIZADO COM SUCESSO")