from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user
from utils.logger import log_erro
from modules.tenant_db import execute_secure
from modules.planos import get_plano_empresa

def superadmin_required(f):

    @wraps(f)
    def wrapper(*args, **kwargs):

        if not current_user.is_superadmin:
            abort(403)

        return f(*args, **kwargs)

    return wrapper


def limite_usuarios_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            # 1. Reutiliza o que você já tem para saber o plano
            plano_atual = get_plano_empresa() 
            tenant_id = current_user.id_empresa
            
            # 2. Define os limites baseados no plano
            limites = {'basico': 10, 'medio': 20, 'premium': 30}
            limite_maximo = limites.get(plano_atual, 10)
            
            # 3. Conta usuários usando sua query segura
            query_count = "SELECT COUNT(*) FROM usuarios WHERE id_empresa = %s"
            resultado = execute_secure(query_count, (tenant_id,), fetch=True)
            total_atual = resultado[0][0] if resultado else 0
            
            # 4. Verifica o limite
            if total_atual >= limite_maximo:
                flash(f"Limite de usuários atingido ({limite_maximo} usuários no plano {plano_atual.upper()}).", "warning")
                # Redireciona para onde o usuário faz o upgrade
                return redirect(url_for("empresas.upgrade_necessario"))
            
            return f(*args, **kwargs)
            
        except Exception as e:
            # Reutiliza sua lógica de erro
            log_erro(f"Erro ao verificar limite de usuários: {e}")
            flash("Erro ao validar permissões do plano.", "danger")
            return redirect(url_for("main.dashboard"))
            
    return wrapper