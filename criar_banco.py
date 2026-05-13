import sqlite3
import os

print("INICIANDO CRIAÇÃO DO BANCO...")

# Garante que a pasta data existe
os.makedirs("data", exist_ok=True)

# Conexão
conexao = sqlite3.connect("data/confeitaria.db")
cursor = conexao.cursor()

# =========================
# MATÉRIA-PRIMA
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS materia_prima (
    id_materia_prima INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    unidade_medida TEXT NOT NULL,
    estoque_minimo REAL DEFAULT 0,
    preco_unitario REAL DEFAULT 0,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================
# PRODUTOS
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS produtos (
    id_produto INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    preco_venda REAL NOT NULL,
    categoria TEXT,
    ativo INTEGER DEFAULT 1,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


# =========================
# DESPESAS (Custos Fixos/Extras)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS despesas (
    id_despesa INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    categoria TEXT,
    data_despesa TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


# =========================
# RECEITAS
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS receitas (
    id_receita INTEGER PRIMARY KEY AUTOINCREMENT,
    id_produto INTEGER NOT NULL,
    id_materia_prima INTEGER NOT NULL,
    quantidade_utilizada REAL NOT NULL,
    FOREIGN KEY (id_produto) REFERENCES produtos(id_produto),
    FOREIGN KEY (id_materia_prima) REFERENCES materia_prima(id_materia_prima)
)
""")

# =========================
# VENDAS (Ajustado para o Dashboard)
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS vendas (
    id_venda INTEGER PRIMARY KEY AUTOINCREMENT,
    data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valor_total REAL DEFAULT 0,
    canal_venda TEXT,
    lucro REAL DEFAULT 0
)
""")

# =========================
# ITENS VENDA
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS itens_venda (
    id_item_venda INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venda INTEGER NOT NULL,
    id_produto INTEGER NOT NULL,
    quantidade INTEGER NOT NULL,
    valor_unitario REAL NOT NULL,
    FOREIGN KEY (id_venda) REFERENCES vendas(id_venda),
    FOREIGN KEY (id_produto) REFERENCES produtos(id_produto)
)
""")

# =========================
# MOVIMENTAÇÃO ESTOQUE
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS movimentacao_estoque (
    id_movimento INTEGER PRIMARY KEY AUTOINCREMENT,
    id_materia_prima INTEGER NOT NULL,
    tipo_movimento TEXT NOT NULL,
    quantidade REAL NOT NULL,
    data_movimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observacao TEXT,
    FOREIGN KEY (id_materia_prima) REFERENCES materia_prima(id_materia_prima)
)
""")

conexao.commit()
conexao.close()

print("Banco de dados configurado com sucesso em data/confeitaria.db!")
