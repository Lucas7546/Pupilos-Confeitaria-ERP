from dotenv import load_dotenv
from modules.db import get_conn

load_dotenv()

with get_conn() as conn:
    with conn.cursor() as cur:

        cur.execute("""
            SELECT *
            FROM movimentacao_estoque
            WHERE id_subproduto IS NOT NULL
            LIMIT 10
        """)

        linhas = cur.fetchall()

        for l in linhas:
            print(l)


    <div class="card">
        <h1>Dashboard</h1>
        </div>
{% endblock %}