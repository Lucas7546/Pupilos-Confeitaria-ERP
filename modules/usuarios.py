from modules.db import conectar
from werkzeug.security import generate_password_hash



PERMISSOES = {

    "admin": [
        "usuarios",
        "estoque",
        "vendas",
        "financeiro",
        "cadastro",
        "auditoria"
    ],

    "gerente": [
        "estoque",
        "vendas",
        "financeiro",
        "cadastro",
        "auditoria"
    ],

    "funcionario": [
        "estoque",
        "vendas"
    ],

    "bloqueado": []
}


# =========================================================
# BUSCAR USUÁRIO
# =========================================================

def buscar_usuario(username):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE username = ?
        AND ativo = 1
    """, (username,))

    usuario = cursor.fetchone()

    conn.close()

    return usuario


# =========================================================
# CRIAR USUÁRIO
# =========================================================

def criar_usuario(username, senha, nivel="funcionario"):

    conn = conectar()
    cursor = conn.cursor()

    # verifica se já existe
    cursor.execute("""
        SELECT id_usuario
        FROM usuarios
        WHERE username = ?
    """, (username,))

    existe = cursor.fetchone()

    if existe:

        conn.close()

        raise Exception("Usuário já existe")

    # gera hash da senha
    senha_hash = generate_password_hash(senha)

    # cria usuário
    cursor.execute("""
        INSERT INTO usuarios (
            username,
            senha,
            nivel
        )
        VALUES (?, ?, ?)
    """, (
        username,
        senha_hash,
        nivel.lower()
    ))

    conn.commit()
    conn.close()


# =========================================================
# ALTERAR SENHA
# =========================================================

def alterar_senha(username, nova_senha):

    conn = conectar()
    cursor = conn.cursor()

    senha_hash = generate_password_hash(nova_senha)

    cursor.execute("""
        UPDATE usuarios
        SET senha = ?
        WHERE username = ?
    """, (
        senha_hash,
        username
    ))

    conn.commit()
    conn.close()


# =========================================================
# LISTAR USUÁRIOS
# =========================================================

def listar_usuarios():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id_usuario,
            username,
            nivel,
            ativo,
            data_cadastro
        FROM usuarios
    """)

    dados = cursor.fetchall()

    conn.close()

    return dados


# =========================================================
# ALTERAR STATUS USUÁRIO
# =========================================================

def alterar_status(id_usuario, ativo):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE usuarios
        SET ativo = ?
        WHERE id_usuario = ?
    """, (
        ativo,
        id_usuario
    ))

    conn.commit()
    conn.close()


# =========================================================
# BUSCAR POR ID
# =========================================================

def buscar_usuario_id(id_usuario):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE id_usuario = ?
    """, (id_usuario,))

    usuario = cursor.fetchone()

    conn.close()

    return usuario