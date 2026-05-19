import psycopg2

URL = "postgresql://auto:1peVWgi0dFxVFmAK0m6ZXoG8wTUuzEto@dpg-d8286f6k1jcs73e67gd0-a.ohio-postgres.render.com/pupilos"

try:
    conn = psycopg2.connect(URL)
    cursor = conn.cursor()

    print("Conectado ao banco com sucesso! Iniciando migração de cargos...")

CREATE TABLE subprodutos (
    id_subproduto SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    unidade_medida TEXT NOT NULL, -- 'kg', 'unidade', 'g'
    preco_custo_kg NUMERIC(10,2) DEFAULT 0.00, -- Calculado automaticamente depois
    estoque_atual NUMERIC(10,3) DEFAULT 0.000,
    estoque_minimo NUMERIC(10,3) DEFAULT 0.000,
    ativo INT DEFAULT 1
);

-- 2. Tabela para a Ficha Técnica do Subproduto (O que vai dentro do Brownie)
CREATE TABLE receitas_subprodutos (
    id_receita_sub SERIAL PRIMARY KEY,
    id_subproduto INT REFERENCES subprodutos(id_subproduto),
    id_materia_prima INT REFERENCES materia_prima(id_materia_prima),
    quantidade_utilizada NUMERIC(10,3) NOT NULL
);


ALTER TABLE receitas ADD COLUMN id_subproduto INT REFERENCES subprodutos(id_subproduto);
-- Agora a tabela receitas pode ter OU o id_materia_prima OU o id_subproduto preenchidos!