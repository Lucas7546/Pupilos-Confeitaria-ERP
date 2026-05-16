import psycopg2
from werkzeug.security import generate_password_hash

def resolver_de_vez():
    # ⚠️ COLOQUE SUA URL EXTERNA DO RENDER AQUI
    URL = "postgresql://auto:1peVWgi0dFxVFmAK0m6ZXoG8wTUuzEto@dpg-d8286f6k1jcs73e67gd0-a.ohio-postgres.render.com/pupilos"
    
    try:
        conn = psycopg2.connect(URL)
        cur = conn.cursor()
        
        # 1. Vamos descobrir quais são os nomes das colunas da sua tabela
        cur.execute("SELECT * FROM usuarios LIMIT 0")
        colunas = [desc[0] for desc in cur.description]
        print(f"As colunas da sua tabela são: {colunas}")

        # Identificando as colunas (tentativa automática)
        col_usuario = 'usuario' if 'usuario' in colunas else 'nome' if 'nome' in colunas else colunas[1]
        col_senha = 'senha' if 'senha' in colunas else colunas[2]
        col_nivel = 'nivel' if 'nivel' in colunas else colunas[3]
        col_ativo = 'ativo' if 'ativo' in colunas else colunas[4]

        senha_hash = generate_password_hash("123") # Senha temporária: 123

        print(f"Limpando usuário '{col_usuario}' = 'amanda'...")
        cur.execute(f"DELETE FROM usuarios WHERE {col_usuario} = %s", ('amanda',))
        
        print(f"Criando 'amanda' como admin na coluna '{col_nivel}'...")
        query = f"INSERT INTO usuarios ({col_usuario}, {col_senha}, {col_nivel}, {col_ativo}) VALUES (%s, %s, %s, %s)"
        cur.execute(query, ('amanda', 741852, 'gerente', 1))
        
        conn.commit()
        print("\n✅ TUDO CERTO!")
        print(f"Login: amanda")
        print(f"Senha: 123")
        print(f"Nível: admin")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    resolver_de_vez()