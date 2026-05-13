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



import psycopg2 # ou sqlite3 se ainda estiver local

def criar_super_admin():
    # Conecte ao seu banco (ajuste os dados se for Postgres)
    conn = psycopg2.connect("sua_url_do_render_aqui")
    cur = conn.cursor()
    
    # 1. Deleta o usuário antigo se ele existir
    cur.execute("DELETE FROM usuarios WHERE usuario = 'amanda'")
    
    # 2. Cria o novo usuário com nível 'admin' e ativo (1)
    # Assumindo a ordem: usuario, senha, nivel, ativo
    cur.execute("""
        INSERT INTO usuarios (usuario, senha, nivel, ativo) 
        VALUES (%s, %s, %s, %s)
    """, ('amanda', '741963', 'gerente', 2))
    
    conn.commit()
    cur.close()
    conn.close()
    print("✔ Super Admin criado com sucesso!")

criar_super_admin()