import psycopg2

URL = "postgresql://auto:1peVWgi0dFxVFmAK0m6ZXoG8wTUuzEto@dpg-d8286f6k1jcs73e67gd0-a.ohio-postgres.render.com/pupilos"

conn = psycopg2.connect(
    URL,
    sslmode="require"
)

cursor = conn.cursor()

# =========================================
# NOVAS COLUNAS IA DELIVERY
# =========================================

try:

    cursor.execute("""
        ALTER TABLE vendas_delivery
        ADD COLUMN tamanho TEXT
    """)

except:
    conn.rollback()

try:

    cursor.execute("""
        ALTER TABLE vendas_delivery
        ADD COLUMN sabores TEXT
    """)

except:
    conn.rollback()

try:

    cursor.execute("""
        ALTER TABLE vendas_delivery
        ADD COLUMN adicionais TEXT
    """)

except:
    conn.rollback()

try:

    cursor.execute("""
        ALTER TABLE vendas_delivery
        ADD COLUMN observacoes TEXT
    """)

except:
    conn.rollback()

conn.commit()

cursor.close()
conn.close()

print("Tabela vendas_delivery atualizada!")