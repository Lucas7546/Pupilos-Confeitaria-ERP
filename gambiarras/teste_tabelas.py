from dotenv import load_dotenv
from modules.tenant_db import get_conn

load_dotenv()

with get_conn() as conn:
    with conn.cursor() as cur:

        # 1. CRIAR TABELA EMPRESAS
        cur.execute("""
            CREATE TABLE IF NOT EXISTS empresas (
                id_empresa SERIAL PRIMARY KEY,
                nome VARCHAR(120) NOT NULL,
                plano VARCHAR(20) DEFAULT 'basic',
                status BOOLEAN DEFAULT TRUE,
                data_criacao TIMESTAMP DEFAULT NOW()
            );
        """)

        conn.commit()

        # 2. LISTAR TABELAS (opcional debug)
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)

        tabelas = cur.fetchall()

        print("TABELAS DO BANCO:")
        for t in tabelas:
            print("-", t[0])