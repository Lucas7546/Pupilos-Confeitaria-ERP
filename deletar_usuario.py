from modules.db import conectar

username = input("Usuário para deletar: ").strip()

conn = conectar()
cursor = conn.cursor()

cursor.execute("""
    DELETE FROM usuarios
    WHERE username = %s
""", (username,))

conn.commit()
conn.close()

print("Usuário deletado com sucesso!")