from dotenv import load_dotenv
import os

load_dotenv()

print("DATABASE_URL:", os.getenv("DATABASE_URL"))

from modules.db import conectar

try:

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
        ORDER BY table_name
    """)

    print("\n===== TABELAS =====\n")

    for tabela in cursor.fetchall():
        print(tabela[0])

except Exception as e:
    print(e)