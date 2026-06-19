from modules.tenant_db import db_conn
import requests
from datetime import datetime, timedelta
from psycopg2.extras import DictCursor
from cryptography.fernet import Fernet
import os

class IfoodAuth:
    def __init__(self):
        self.url = "https://merchant-api.ifood.com.br/authentication/v1.0/oauth/token"
        # Carrega a chave de criptografia do ambiente
        self.cipher = Fernet(os.getenv("DB_ENCRYPTION_KEY").encode())

    def get_token(self, id_empresa):
        # 1. Busca credenciais e token atual no banco
        with db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT client_id, client_secret, access_token, expires_at 
                    FROM integracao_ifood_config 
                    WHERE id_empresa = %s
                """, (id_empresa,))
                row = cur.fetchone()
        
        if not row:
            raise Exception(f"Configurações iFood não encontradas para empresa {id_empresa}")

        # 2. Se achou um token e ele ainda é válido (margem de 60 segundos)
        if row['access_token'] and row['expires_at'] and row['expires_at'] > (datetime.now() + timedelta(seconds=60)):
            return row['access_token']

        # 3. Descriptografa o secret para poder usar na autenticação
        client_secret_descriptografado = self.cipher.decrypt(row['client_secret'].encode()).decode()

        # 4. Gera um novo token usando o secret real
        novo_token_data = self._fetch_new_token(row['client_id'], client_secret_descriptografado)
        
        token = novo_token_data['accessToken']
        expires_in = novo_token_data['expiresIn']
        expiracao = datetime.now() + timedelta(seconds=expires_in)

        # 5. Atualiza o banco com o novo token
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE integracao_ifood_config 
                    SET access_token = %s, expires_at = %s 
                    WHERE id_empresa = %s
                """, (token, expiracao, id_empresa))
                
        return token

    def _fetch_new_token(self, client_id, client_secret):
        payload = {
            "grantType": "client_credentials",
            "clientId": client_id,
            "clientSecret": client_secret
        }
        response = requests.post(self.url, data=payload)
        if response.status_code == 200:
            return response.json()
        
        raise Exception(f"Erro ao autenticar no iFood: {response.text}")

# Instância única para ser importada
ifood_auth = IfoodAuth()