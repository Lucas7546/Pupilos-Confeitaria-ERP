import psycopg2

# 1. COLE AQUI sua "External Database URL" que está no painel do Render
DATABASE_URL = "postgresql://auto:1peVWgi0dFxVFmAK0m6ZXoG8wTUuzEto@dpg-d8286f6k1jcs73e67gd0-a.ohio-postgres.render.com/pupilos"

try:
    # Conectando ao banco
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # 2. Esse comando lista TODAS as colunas que existem na tabela usuarios
    cursor.execute("SELECT * FROM usuarios LIMIT 0")
    nomes_colunas = [desc[0] for desc in cursor.description]
    
    print("--- ESTRUTURA ENCONTRADA ---")
    print(f"As colunas da sua tabela são: {nomes_colunas}")
    print("-" * 30)

    # 3. Tenta listar os dados de todos os usuários
    cursor.execute("SELECT * FROM usuarios")
    dados = cursor.fetchall()

    print("--- DADOS DOS USUÁRIOS ---")
    if not dados:
        print("Nenhum usuário cadastrado.")
    for linha in dados:
        print(linha)

    conn.close()

except Exception as e:
    print(f"ERRO AO CONECTAR: {e}")