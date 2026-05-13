import os
import psycopg2
from werkzeug.security import generate_password_hash

# Conecta ao banco (certifique-se de que o $env:DATABASE_URL ainda está ativo no terminal)
conn = psycopg2.connect(os.environ["DATABASE_URL"], sslmode='require')
cursor = conn.cursor()

nova_senha = generate_password_hash("SUA_NOVA_SENHA_AQUI")
usuario = "admin" # ou "amanda"

cursor.execute("UPDATE usuarios SET senha = %s WHERE username = %s", (nova_senha, usuario))

conn.commit()
print(f"Senha de {usuario} alterada com sucesso!")
conn.close()