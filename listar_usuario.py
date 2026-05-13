import os
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"], sslmode='require')
cursor = conn.cursor()

# Isso vai te mostrar exatamente como os nomes estão escritos no banco
cursor.execute("SELECT username FROM usuarios")
usuarios = cursor.fetchall()

print("Usuários encontrados no banco:")
for u in usuarios:
    print(f"- '{u[0]}'")

conn.close()