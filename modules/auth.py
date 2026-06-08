from modules.usuarios import buscar_usuario
from werkzeug.security import check_password_hash
from ape.extensions import User


def validar_login(username: str, senha: str):
    usuario = buscar_usuario(username)
    
    if not usuario:
        print(f"LOGIN ERRO: Usuário '{username}' não encontrado.")
        return None

    # Verifica se os campos que você passou estão vindo corretamente
    print(f"DEBUG LOGIN: Usuário encontrado: {usuario.get('username')}")
    print(f"DEBUG LOGIN: Ativo: {usuario.get('ativo')}, ID Empresa: {usuario.get('id_empresa')}")
    
    if not usuario.get("ativo"):
        print(f"LOGIN ERRO: Usuário '{username}' está inativo no banco.")
        return None

    # Teste de senha
    senha_hash_banco = usuario.get("senha")
    if check_password_hash(senha_hash_banco, senha):
        print(f"LOGIN SUCESSO: Senha validada para '{username}'.")
        return User(usuario)
    else:
        print(f"LOGIN ERRO: Hash da senha não confere.")
        print(f"DEBUG: Hash no banco: {senha_hash_banco}")
        return None