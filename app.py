Python
import os
import json
import pandas as pd
import io
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, flash, abort, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

# Importação dos seus módulos (Certifique-se que todos usam psycopg2)
from modules import usuarios, vendas, estoque, produtos, receitas
from modules.permissoes import acesso_requerido

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "pupilos-confeitaria-senha-segura-2026")

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# ========================================================
# SISTEMA DE LOGS (Migrado para PostgreSQL via módulo usuarios)
# ========================================================

def registrar_log(acao, modulo, detalhe="", usuario_manual=None):
    """Registra atividades no banco de dados e no console para depuração."""
    usuario_log = usuario_manual or (current_user.id if current_user.is_authenticated else "anonimo")
    
    try:
        # Usando a função que você já deve ter no seu módulo de banco de dados
        usuarios.registrar_log_db(usuario_log, acao, modulo, detalhe)
    except Exception as e:
        print(f"ERRO CRÍTICO AO SALVAR LOG: {e}")

# ========================================================
# ROTAS DE AUTENTICAÇÃO
# ========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        senha = request.form["senha"].strip()

        usuario = usuarios.buscar_usuario(username)

        if usuario and check_password_hash(usuario[2], senha):
            # Verifica se está ativo (assumindo que usuario[4] é o status)
            if len(usuario) > 4 and usuario[4] == 0:
                flash("Usuário bloqueado. Fale com o administrador.", "danger")
                return render_template("login.html")

            user = User(username)
            login_user(user)
            registrar_log("LOGIN", "AUTH", f"Usuário {username} logou")
            flash("Bem-vindo(a)!", "success")
            return redirect("/")
        
        flash("Usuário ou senha inválidos", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    registrar_log("LOGOUT", "AUTH", f"Usuário {current_user.id} saiu")
    logout_user()
    return redirect("/login")

# ========================================================
# DASHBOARD
# ========================================================

@app.route("/")
@login_required
def dashboard():
    resumo_semanal = vendas.obter_resumo_periodo(dias=7)
    resumo_mensal = vendas.obter_resumo_periodo(dias=30)
    capacidade = produtos.calcular_capacidade_geral()
    insumos = estoque.listar_materia_prima()
    criticos = [i for i in insumos if i[4] <= i[3]]

    return render_template(
        "dashboard.html",
        semana=resumo_semanal,
        mes=resumo_mensal,
        capacidade=capacidade,
        criticos=criticos
    )

# ========================================================
# GESTÃO DE ESTOQUE
# ========================================================

@app.route("/estoque")
@login_required
@acesso_requerido("estoque")
def pagina_estoque():
    dados = estoque.listar_materia_prima()
    return render_template("estoque.html", materias=dados)

@app.route("/compras")
@login_required
def pagina_compras():
    return render_template("compras.html", materias=estoque.listar_materia_prima())

@app.route("/registrar-compra", methods=["POST"])
@login_required
def registrar_compra():
    try:
        id_mp = int(request.form["id_materia_prima"])
        qtd = float(request.form["quantidade"].replace(",", "."))
        preco_total = float(request.form["preco_total"].replace(",", "."))
        
        preco_unitario = preco_total / qtd
        estoque.entrada_estoque(id_mp, qtd)
        estoque.atualizar_preco_mp(id_mp, preco_unitario)

        registrar_log("COMPRA", "ESTOQUE", f"MP ID {id_mp} | Qtd {qtd}")
        flash("Compra registrada!", "success")
    except Exception as e:
        flash(f"Erro: {e}", "danger")
    return redirect("/estoque")

# ========================================================
# VENDAS
# ========================================================

@app.route("/vendas")
@login_required
@acesso_requerido("vendas")
def pagina_vendas():
    return render_template("vendas.html", produtos=produtos.buscar_produto_por_nome(""))

@app.route("/vender", methods=["POST"])
@login_required
def vender():
    try:
        id_p = int(request.form["id_produto"])
        qtd = int(request.form["quantidade"])
        
        produto_info = next((p for p in produtos.buscar_produto_por_nome("") if p[0] == id_p), None)
        if not produto_info:
            flash("Produto não encontrado", "danger")
            return redirect("/vendas")

        sucesso, mensagem = vendas.vender_produto(id_p, qtd, produto_info[2])
        if sucesso:
            registrar_log("VENDA", "VENDAS", f"Produto {id_p} | Qtd {qtd}")
            flash(mensagem, "success")
        else:
            flash(mensagem, "danger")
    except Exception as e:
        flash(f"Erro: {e}", "danger")
    return redirect("/vendas")

# ========================================================
# FINANCEIRO E AUDITORIA
# ========================================================

@app.route("/financeiro")
@login_required
@acesso_requerido("financeiro")
def pagina_financeiro():
    faturamento = vendas.obter_resumo_periodo(30)["faturamento"]
    custo_insumos = vendas.obter_custo_total_vendas(30)
    despesas = vendas.listar_despesas(30)
    total_fixas = sum([d[2] for d in despesas])
    
    return render_template(
        "financeiro.html",
        faturamento=faturamento,
        custo_insumos=custo_insumos,
        despesas=despesas,
        total_fixas=total_fixas,
        lucro_real=(faturamento - custo_insumos - total_fixas)
    )

@app.route("/auditoria")
@login_required
@acesso_requerido("auditoria")
def auditoria():
    # Pega logs direto do Postgres agora
    logs_data = usuarios.listar_logs_auditoria(100)
    return render_template('auditoria.html', logs=logs_data)

# ========================================================
# GESTÃO DE USUÁRIOS (SÓ ADMIN)
# ========================================================

@app.route("/usuarios")
@login_required
@acesso_requerido("usuarios")
def pagina_usuarios():
    return render_template("usuarios.html", usuarios_lista=usuarios.listar_usuarios())

@app.route("/criar-usuario", methods=["POST"])
@login_required
@acesso_requerido("usuarios")
def criar_usuario():
    user = request.form["username"].strip().lower()
    passw = request.form["senha"].strip()
    nivel = request.form["nivel"]
    
    if len(passw) < 6:
        flash("Senha curta demais!", "danger")
    else:
        hash_senha = generate_password_hash(passw)
        usuarios.criar_usuario(user, hash_senha, nivel)
        registrar_log("CRIAR_USER", "USUARIOS", f"Criou {user}")
        flash("Usuário criado!", "success")
    return redirect("/usuarios")

@app.route("/toggle-usuario/<int:id_usuario>")
@login_required
@acesso_requerido("usuarios")
def toggle_usuario(id_usuario):
    user_db = usuarios.buscar_usuario_id(id_usuario)
    if user_db:
        # Se status (índice 4) for 1, vira 0. Se for 0, vira 1.
        novo_status = 0 if user_db[4] == 1 else 1
        usuarios.alterar_status(id_usuario, novo_status)
        flash("Status alterado!", "success")
    return redirect("/usuarios")

# ========================================================
# IMPORTAÇÃO IFOOD E ESTRUTURA
# ========================================================

@app.route("/importacoes")
@login_required
def central_importacoes():
    return render_template("central_importacoes.html")

@app.route("/importar-ifood", methods=["POST"])
@login_required
def importar_ifood():
    # Lógica simplificada de importação
    arquivo = request.files.get("arquivo")
    if arquivo:
        registrar_log("IMPORT_IFOOD", "VENDAS", f"Arquivo: {arquivo.filename}")
        flash("Processamento de iFood iniciado!", "info")
    return redirect("/importacoes")

# ========================================================
# INICIALIZAÇÃO
# ========================================================

if __name__ == "__main__":
    # O Render usa a variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)