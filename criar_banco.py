import os
import psycopg2
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

print("INICIANDO CRIAÇÃO DO BANCO POSTGRES (VERSÃO ROBUSTA)...")

# carrega .env (só localmente)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL não encontrada!")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()
# =========================================================
# 1. USUÁRIOS (Sem alteração de colunas)
# =========================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    senha TEXT NOT NULL,
    nivel TEXT DEFAULT 'funcionario',
    ativo INTEGER DEFAULT 1,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# 2. MATÉRIA-PRIMA (Sem alteração de colunas)
# =========================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS materia_prima (
    id_materia_prima SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    unidade_medida TEXT NOT NULL,
    estoque_minimo REAL DEFAULT 0,
    preco_unitario REAL DEFAULT 0,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# 3. PRODUTOS (Sem alteração de colunas)
# =========================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS produtos (
    id_produto SERIAL PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    preco_venda REAL DEFAULT 0,
    categoria TEXT,
    ativo INTEGER DEFAULT 1,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# 4. RECEITAS (Adicionado: Vínculo com Produto e Matéria-Prima)
# =========================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS receitas (
    id_receita SERIAL PRIMARY KEY,
    id_produto INTEGER REFERENCES produtos(id_produto) ON DELETE CASCADE,
    id_materia_prima INTEGER REFERENCES materia_prima(id_materia_prima) ON DELETE RESTRICT,
    quantidade_utilizada REAL NOT NULL
)
""")

# =========================================================
# 5. VENDAS (Sem alteração de colunas)
# =========================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS vendas (
    id_venda SERIAL PRIMARY KEY,
    data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valor_total REAL DEFAULT 0,
    lucro REAL DEFAULT 0,
    canal_venda TEXT,
    usuario TEXT
)
""")

# =========================================================
# 6. ITENS VENDA (Adicionado: Vínculo com Venda e Produto)
# =========================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS itens_venda (
    id_item_venda SERIAL PRIMARY KEY,
    id_venda INTEGER REFERENCES vendas(id_venda) ON DELETE CASCADE,
    id_produto INTEGER REFERENCES produtos(id_produto) ON DELETE SET NULL,
    quantidade INTEGER,
    valor_unitario REAL
)
""")

# =========================================================
# 7. MOVIMENTAÇÃO ESTOQUE (Adicionado: Vínculo com Matéria-Prima)
# =========================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS movimentacao_estoque (
    id_movimento SERIAL PRIMARY KEY,
    id_materia_prima INTEGER REFERENCES materia_prima(id_materia_prima) ON DELETE CASCADE,
    tipo_movimento TEXT,
    quantidade REAL,
    observacao TEXT,
    usuario TEXT,
    data_movimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# 8. LOGS E DESPESAS (Mantidos originais)
# =========================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id_log SERIAL PRIMARY KEY,
    usuario TEXT, acao TEXT, modulo TEXT, detalhe TEXT, 
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS despesas (
    id_despesa SERIAL PRIMARY KEY,
    descricao TEXT, valor REAL, categoria TEXT, 
    data_despesa TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# =========================================================
# ADMIN (Com correção para atualização de senha se necessário)
# =========================================================
senha_admin = generate_password_hash("123456")
cursor.execute("""
INSERT INTO usuarios (username, senha, nivel)
VALUES (%s, %s, %s)
ON CONFLICT (username) DO NOTHING
""", ("admin", senha_admin, "admin"))

# =========================================================
# sistema
# =========================================================

cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresa_config (
            id SERIAL PRIMARY KEY,
            regime_fiscal VARCHAR(50) DEFAULT 'MEI'
        )
    """)
# =========================================================
# FINALIZAÇÃO
# =========================================================
conn.commit()
cursor.close()
conn.close()

print("BANCO POSTGRES ATUALIZADO COM SUCESSO!")
