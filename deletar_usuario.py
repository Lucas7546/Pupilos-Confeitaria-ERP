import psycopg2

# 1. COLE AQUI sua "External Database URL" do Render
DATABASE_URL = "postgresql://auto:1peVWgi0dFxVFmAK0m6ZXoG8wTUuzEto@dpg-d8286f6k1jcs73e67gd0-a.ohio-postgres.render.com/pupilos"

def excluir_por_terminal():
    print("=== EXCLUSOR DE USUÁRIOS (NUVEM) ===")
    
    # Vamos pedir o nome do usuário para facilitar sua vida
    username = input("Digite o 'username' de quem deseja excluir: ").strip().lower()

    if not username:
        print("❌ Você precisa digitar um nome.")
        return

    confirmacao = input(f"⚠️ TEM CERTEZA que deseja apagar '{username}'? (sim/não): ").strip().lower()
    if confirmacao != 'sim':
        print("Ufa! Operação cancelada.")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Primeiro verificamos se o cara existe
        cur.execute("SELECT id_usuario FROM usuarios WHERE username = %s", (username,))
        resultado = cur.fetchone()

        if not resultado:
            print(f"❌ Usuário '{username}' não foi encontrado no banco.")
            return

        # Se existe, deletamos
        cur.execute("DELETE FROM usuarios WHERE username = %s", (username,))
        
        conn.commit()
        print(f"\n✔ Usuário '{username}' foi removido com sucesso do banco do Render!")

    except Exception as e:
        print(f"❌ Erro ao conectar ou excluir: {e}")
    finally:
        if 'conn' in locals():
            cur.close()
            conn.close()

if __name__ == "__main__":
    excluir_por_terminal()