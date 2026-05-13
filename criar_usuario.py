from modules import usuarios

print("=== CRIAR USUÁRIO ===")

username = input("Nome do usuário: ").strip()
senha = input("Senha: ").strip()
nivel = input("Nível (admin/gerente/funcionario): ").strip().lower()

# valida nível
if nivel not in ["admin", "gerente", "funcionario"]:
    print("❌ Nível inválido")
    exit()

# verifica se já existe
usuario_existente = usuarios.buscar_usuario(username)

if usuario_existente:
    print("❌ Usuário já existe no sistema!")
    exit()

# cria usuário
usuarios.criar_usuario(username, senha, nivel)

print("\n✔ Usuário criado com sucesso!")