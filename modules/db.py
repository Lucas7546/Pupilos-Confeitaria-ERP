import os
import psycopg2

def conectar():
    """Faz a ponte de conexão usando a URL do Render."""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        raise Exception("Variável DATABASE_URL não encontrada!")

    # O segredo para o Render é o sslmode='require'
    return psycopg2.connect(database_url, sslmode='require')