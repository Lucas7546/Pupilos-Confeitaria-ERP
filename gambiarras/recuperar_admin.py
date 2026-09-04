import os
import psycopg2
from dotenv import load_dotenv

# Carrega as variáveis do .env que está na raiz do projeto
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL não encontrada no .env")
    exit()

# Garante SSL para o PostgreSQL
if "sslmode=" not in DATABASE_URL:
    DATABASE_URL += "&sslmode=require" if "?" in DATABASE_URL else "?sslmode=require"

try:
    print("🔌 Conectando ao banco atual...")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id_usuario,
            username,
            nivel,
            id_empresa,
            ativo,
            is_superadmin
        FROM usuarios
        WHERE nivel = 'admin'
        ORDER BY id_usuario;
    """)

    usuarios = cur.fetchall()

    print("\n" + "=" * 50)
    print("        USUÁRIOS ADMINISTRADORES")
    print("=" * 50)

    if not usuarios:
        print("❌ Nenhum usuário com nível 'admin' encontrado.")
    else:
        for usuario in usuarios:
            print(f"""
ID usuário    : {usuario[0]}
Username      : {usuario[1]}
Nível         : {usuario[2]}
ID empresa    : {usuario[3]}
Ativo         : {usuario[4]}
Superadmin    : {usuario[5]}
""")
            print("-" * 50)

    cur.close()
    conn.close()

    print("\n✅ Consulta concluída.")

except Exception as e:
    print(f"\n❌ ERRO AO CONECTAR OU CONSULTAR:")
    print(e)