import os
import json

def inject_empresa():
    cliente = os.getenv("CLIENTE", "").strip().lower()
    
    # Ajuste o caminho conforme a estrutura da sua pasta
    # Usando o caminho absoluto do projeto facilita
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "clientes", cliente, "config.json")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return {"EMPRESA": config.get("NOME_EMPRESA", "Nome Padrão")}
        except (json.JSONDecodeError, Exception):
            return {"EMPRESA": "Nome Padrão"}
    
    return {"EMPRESA": "Nome Padrão"}