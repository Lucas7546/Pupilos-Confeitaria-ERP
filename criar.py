import psycopg2

URL = "postgresql://auto:1peVWgi0dFxVFmAK0m6ZXoG8wTUuzEto@dpg-d8286f6k1jcs73e67gd0-a.ohio-postgres.render.com/pupilos"

try:
    conn = psycopg2.connect(URL)
    cursor = conn.cursor()

    print("Conectado ao banco com sucesso! Iniciando migração de cargos...")

    # Se a coluna 'nivel' for um ENUM, precisamos adicionar os novos valores antes de atualizar os usuários
    # O 'IF NOT EXISTS' evita erros caso você rode o script mais de uma vez
    try:
        cursor.execute("ALTER TYPE nivel_usuario_enum ADD VALUE IF NOT EXISTS 'socios';")
        cursor.execute("ALTER TYPE nivel_usuario_enum ADD VALUE IF NOT EXISTS 'colaborador';")
        print("-> Tipos ENUM atualizados com sucesso (caso existam).")
    except Exception:
        # Se sua coluna for apenas VARCHAR comum (texto), ele vai ignorar esse bloco e seguir em frente
        conn.rollback() 

    # 1. Atualiza os Gerentes para Sócios
    cursor.execute("UPDATE usuarios SET nivel = 'socios' WHERE nivel = 'gerente';")
    print("-> Gerentes atualizados para Sócios.")

    # 2. Atualiza os Funcionários para Colaboradores
    cursor.execute("UPDATE usuarios SET nivel = 'colaborador' WHERE nivel = 'funcionario';")
    print("-> Funcionários atualizados para Colaboradores.")

    conn.commit()
    print("\nBanco de dados atualizado com sucesso!")

except Exception as e:
    print(f"\n[ERRO NO SCRIPT]: {e}")
    if 'conn' in locals():
        conn.rollback()

finally:
    if 'cursor' in locals() and cursor is not None:
        cursor.close()
    if 'conn' in locals() and conn is not None:
        conn.close()