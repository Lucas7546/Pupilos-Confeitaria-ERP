from dotenv import load_dotenv
from modules.db import conectar

load_dotenv()

try:

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)

    tabelas = cursor.fetchall()

    print("\n===== TABELAS DO BANCO =====\n")

    for tabela in tabelas:
        print(tabela[0])

    print("\n===== TOTAL =====")
    print(len(tabelas), "tabelas encontradas.")

except Exception as e:
    print("ERRO:")
    print(e)