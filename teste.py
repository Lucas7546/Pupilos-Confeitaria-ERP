from dotenv import load_dotenv
from modules.db import get_conn

load_dotenv()

tabelas = [
    "aliases_produtos",
    "despesas",
    "empresa_config",
    "itens_venda",
    "logs",
    "materia_prima",
    "movimentacao_estoque",
    "movimentacao_produtos",
    "produtos",
    "receitas",
    "receitas_subprodutos",
    "sabores",
    "subprodutos",
    "tamanhos",
    "usuarios",
    "vendas",
    "vendas_delivery"
]

with get_conn() as conn:
    with conn.cursor() as cur:

        for tabela in tabelas:
            try:
                cur.execute(f"""
                    ALTER TABLE {tabela}
                    ADD COLUMN IF NOT EXISTS id_empresa INT;
                """)
                print(f"OK -> {tabela}")

            except Exception as e:
                print(f"ERRO -> {tabela}: {e}")

        conn.commit()