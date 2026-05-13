import sqlite3
import os

print("🚀 INICIANDO CRIAÇÃO DO BANCO (MANTENDO NOMES ORIGINAIS)...")

# Cria pasta data se não existir
os.makedirs("data", exist_ok=True)

# Se quiser deletar o banco antigo para garantir que as tabelas venham com as colunas novas:
# if os.path.exists("data/confeitaria.db"): os.remove("data/confeitaria.db")

conexao = sqlite3.connect("data/pupilos_confeitaria.db")
cursor = conexao.cursor()

# 1. MATÉRIA PRIMA (Criar antes por causa das Foreign Keys)
cursor.execute("""
CREATE TABLE IF NOT EXISTS materia_prima (
    id_materia_prima INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    unidade_medida TEXT,
    estoque_atual REAL DEFAULT 0,
    estoque_minimo REAL DEFAULT 0
)
""")

# 2. USUÁRIOS
cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL,
    nivel TEXT DEFAULT 'admin',
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# 3. LOGS DO SISTEMA (Mantive 'id_log' conforme suas funções atuais)
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

# 4. PRODUTOS
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

# 5. RECEITAS
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

# 6. VENDAS
cursor.execute("""
CREATE TABLE IF NOT EXISTS vendas (
    id_venda INTEGER PRIMARY KEY AUTOINCREMENT,
    data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valor_total REAL DEFAULT 0,
    canal_venda TEXT,
    lucro REAL DEFAULT 0
)
""")

# 7. ITENS VENDA
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

# 8. MOVIMENTAÇÃO ESTOQUE
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

# 9. DESPESAS
cursor.execute("""
CREATE TABLE IF NOT EXISTS despesas (
    id_despesa INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    categoria TEXT,
    data_despesa TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conexao.commit()
conexao.close()

print("✅ BANCO CRIADO COM SUCESSO E COMPATÍVEL COM SUAS FUNÇÕES!")