import sqlite3
import os
from werkzeug.security import generate_password_hash

print("INICIANDO CRIAÇÃO DO BANCO...")

# =========================================================
# GARANTE PASTA DATA
# =========================================================

os.makedirs("data", exist_ok=True)

# =========================================================
# CONEXÃO
# =========================================================

conexao = sqlite3.connect("data/confeitaria.db")
cursor = conexao.cursor()

# =========================================================
# USUÁRIOS
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    senha TEXT NOT NULL,
    nivel TEXT DEFAULT 'funcionario',
    ativo INTEGER DEFAULT 1,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# LOGS
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id_log INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT,
    acao TEXT,
    modulo TEXT,
    detalhe TEXT,
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# MATÉRIA-PRIMA
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS materia_prima (
    id_materia_prima INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    unidade_medida TEXT NOT NULL,
    estoque_minimo REAL DEFAULT 0,
    preco_unitario REAL DEFAULT 0,
    estoque_atual REAL DEFAULT 0,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# PRODUTOS
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS produtos (
    id_produto INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    preco_venda REAL DEFAULT 0,
    categoria TEXT,
    ativo INTEGER DEFAULT 1,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# RECEITAS
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS receitas (
    id_receita INTEGER PRIMARY KEY AUTOINCREMENT,
    id_produto INTEGER NOT NULL,
    id_materia_prima INTEGER NOT NULL,
    quantidade_utilizada REAL NOT NULL,

    FOREIGN KEY (id_produto)
        REFERENCES produtos(id_produto),

    FOREIGN KEY (id_materia_prima)
        REFERENCES materia_prima(id_materia_prima)
)
""")

# =========================================================
# VENDAS
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS vendas (
    id_venda INTEGER PRIMARY KEY AUTOINCREMENT,
    data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valor_total REAL DEFAULT 0,
    lucro REAL DEFAULT 0,
    canal_venda TEXT,
    usuario TEXT
)
""")

# =========================================================
# ITENS VENDA
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS itens_venda (
    id_item_venda INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venda INTEGER NOT NULL,
    id_produto INTEGER NOT NULL,
    quantidade INTEGER NOT NULL,
    valor_unitario REAL NOT NULL,

    FOREIGN KEY (id_venda)
        REFERENCES vendas(id_venda),

    FOREIGN KEY (id_produto)
        REFERENCES produtos(id_produto)
)
""")

# =========================================================
# MOVIMENTAÇÃO ESTOQUE
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS movimentacao_estoque (
    id_movimento INTEGER PRIMARY KEY AUTOINCREMENT,
    id_materia_prima INTEGER NOT NULL,
    tipo_movimento TEXT NOT NULL,
    quantidade REAL NOT NULL,
    observacao TEXT,
    usuario TEXT,
    data_movimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (id_materia_prima)
        REFERENCES materia_prima(id_materia_prima)
)
""")

# =========================================================
# DESPESAS
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS despesas (
    id_despesa INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    categoria TEXT,
    data_despesa TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# CRIA ADMIN MASTER
# =========================================================

senha_admin = generate_password_hash("123456")

cursor.execute("""
INSERT OR IGNORE INTO usuarios (
    username,
    senha,
    nivel
)
VALUES (?, ?, ?)
""", (
    "admin",
    senha_admin,
    "admin"
))

# =========================================================
# FINALIZA
# =========================================================

conexao.commit()
conexao.close()

print("BANCO CRIADO COM SUCESSO!")
print("Usuário padrão:")
print("Login: admin")
print("Senha: 123456")
