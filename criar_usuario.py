import psycopg2
from werkzeug.security import generate_password_hash

# 1. COLOQUE AQUI sua "External Database URL" do Render
DATABASE_URL = "postgresql://auto:1peVWgi0dFxVFmAK0m6ZXoG8wTUuzEto@dpg-d8286f6k1jcs73e67gd0-a.ohio-postgres.render.com/pupilos"

def criar_novo_usuario():
    print("=== GERENCIADOR DE USUÁRIOS (NUVEM) ===")

    username = input("Nome do usuário: ").strip().lower()
    senha = input("Senha: ").strip()
    nivel = input("Nível (admin/gerente/funcionario): ").strip().lower()

    if nivel not in ["admin", "gerente", "funcionario"]:
        print("❌ Nível inválido")
        return

    # Gerar o hash da senha (IGUAL o seu site faz)
    senha_hash = generate_password_hash(senha)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 2. Verifica se já existe (usando a coluna correta 'username')
        cur.execute("SELECT id_usuario FROM usuarios WHERE username = %s", (username,))
        if cur.fetchone():
            print(f"❌ O usuário '{username}' já existe no banco do Render!")
            return

        # 3. Cria o usuário com a estrutura que vimos no seu banco
        # Colunas: username, senha, nivel, ativo
        query = """
            INSERT INTO usuarios (username, senha, nivel, ativo, data_cadastro) 
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        """
        cur.execute(query, (username, senha_hash, nivel, 1))
        
        conn.commit()
        print(f"\n✔ Usuário '{username}' criado com sucesso no banco do Render!")

    except Exception as e:
        print(f"❌ Erro ao conectar ou salvar: {e}")
    finally:
        if 'conn' in locals():
            cur.close()
            conn.close()

if __name__ == "__main__":
    criar_novo_usuario()