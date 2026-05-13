import os
import psycopg2
from werkzeug.security import generate_password_hash

# Conecta ao banco (Lembre-se do $env:DATABASE_URL no terminal)
conn = psycopg2.connect(os.environ["DATABASE_URL"], sslmode='require')
cursor = conn.cursor()

# 1. Defina aqui a senha que VOCÊ quer usar
senha_texto_claro = "741963" 
hash_da_senha = generate_password_hash(senha_texto_claro)

# 2. O 'WHERE' garante que APENAS o admin seja afetado
usuario_alvo = "amanda"

cursor.execute("""
    UPDATE usuarios 
    SET senha = %s 
    WHERE username = %s
""", (hash_da_senha, usuario_alvo))

conn.commit()

# Verifica se alguém foi realmente alterado
if cursor.rowcount > 0:
    print(f"Sucesso! A senha de '{usuario_alvo}' foi atualizada.")
else:
    print(f"Erro: Usuário '{usuario_alvo}' não encontrado. Verifique se o nome está correto.")

cursor.close()
conn.close()