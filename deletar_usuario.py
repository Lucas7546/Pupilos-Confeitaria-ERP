from modules.db import conectar

conn = conectar()
cursor = conn.cursor()

cursor.execute("""
    DELETE FROM usuarios
    WHERE username = ?
""", ("amanda",))

conn.commit()
conn.close()

print("Usuário removido!")