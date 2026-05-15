import psycopg2

URL = "postgresql://auto:1peVWgi0dFxVFmAK0m6ZXoG8wTUuzEto@dpg-d8286f6k1jcs73e67gd0-a.ohio-postgres.render.com/pupilos"

conn = psycopg2.connect(URL)
cursor = conn.cursor()

# cria tabela
cursor.execute("""
CREATE TABLE IF NOT EXISTS empresa_config (
    id SERIAL PRIMARY KEY,
    regime_fiscal VARCHAR(50) DEFAULT 'MEI'
)
""")

# insere padrão
cursor.execute("""
INSERT INTO empresa_config (regime_fiscal)
VALUES ('MEI')
ON CONFLICT DO NOTHING
""")

conn.commit()
cursor.close()
conn.close()

print("empresa_config criada com sucesso!")