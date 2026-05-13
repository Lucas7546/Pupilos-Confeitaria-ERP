from dotenv import load_dotenv
load_dotenv()
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask import Flask, render_template, request, redirect, flash, session, abort
from datetime import datetime
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
import json
import pandas as pd
import os
import io

# Importando seus módulos revisados
from modules import usuarios, vendas, estoque, produtos, receitas
from modules.permissoes import acesso_requerido
from modules.db import conectar

# ========================================================
# APP INIT
# ========================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "pupilos-confeitaria-123")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ========================================================
# LOGS (Apenas Postgres para evitar erro de permissão no Render)
# ========================================================

def registrar_log(acao, modulo, detalhe="", usuario_manual=None):
    usuario_log = usuario_manual or (current_user.id if current_user.is_authenticated else "anonimo")
    conn = None
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO logs (usuario, acao, modulo, detalhe)
            VALUES (%s, %s, %s, %s)
        """, (str(usuario_log), acao, modulo, detalhe))
        conn.commit()
    except Exception as e:
        print(f"Erro DB log: {e}")
    finally:
        if conn: conn.close()

# ========================================================
# USER CLASS
# ========================================================

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# ========================================================
# ROTAS PRINCIPAIS (Login, Logout, Dashboard)
# ========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        senha = request.form["senha"].strip()

        usuario = usuarios.buscar_usuario(username)

        # Suporta tanto hash quanto senha pura para seu teste inicial
        if usuario:
            if check_password_hash(usuario[2], senha) or usuario[2] == senha:
                login_user(User(username))
                registrar_log("LOGIN", "AUTH", f"{username} entrou")
                return redirect("/")
        
        flash("Usuário ou senha inválidos", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    registrar_log("LOGOUT", "AUTH", f"{current_user.id} saiu")
    logout_user()
    return redirect("/login")

@app.route("/")
@login_required
# Removi o acesso_requerido temporariamente para você conseguir entrar
def dashboard():
    try:
        semana = vendas.obter_resumo_periodo(7)
        mes = vendas.obter_resumo_periodo(30)
        insumos = estoque.listar_materia_prima()
        criticos = [i for i in insumos if i[5] == "BAIXO"]
    except Exception as e:
        print(f"Erro no dashboard: {e}")
        semana, mes, criticos = {}, {}, []

    return render_template(
        "dashboard.html",
        semana=semana,
        mes=mes,
        criticos=criticos
    )

@app.route("/usuarios/editar/<int:id>", methods=["POST"])
@login_required
@acesso_requerido("usuarios")
def editar_usuario(id):
    nova_senha = request.form.get("nova_senha")
    if nova_senha:
        hash_senha = generate_password_hash(nova_senha)
        usuarios.atualizar_senha(id, hash_senha) 
        flash("Senha alterada!", "success")
    return redirect("/usuarios")

# ========================================================
# COMPRAS E ESTOQUE
# ========================================================

@app.route("/estoque")
@login_required
@acesso_requerido("estoque")
def estoque_page():
    dados = estoque.listar_materia_prima()
    return render_template("estoque.html", materias=dados)

@app.route("/registrar-compra", methods=["POST"])
@login_required
def registrar_compra():
    try:
        id_mp = int(request.form["id_materia_prima"])
        qtd = float(request.form["quantidade"].replace(",", "."))
        total = float(request.form["preco_total"].replace(",", "."))

        if estoque.registrar_compra_estoque(id_mp, qtd, total):
            flash("Compra registrada e custo atualizado!", "success")
            registrar_log("COMPRA", "ESTOQUE", f"ID MP: {id_mp} | Qtd: {qtd}")
        else:
            flash("Erro ao registrar compra.", "danger")
    except Exception as e:
        flash(f"Erro: {str(e)}", "danger")
    return redirect("/estoque")

# ========================================================
# VENDAS E FINANCEIRO
# ========================================================

@app.route("/vendas")
@login_required
@acesso_requerido("vendas")
def vendas_page():
    prods = produtos.listar_produtos()
    recente = vendas.listar_vendas_recentes(20)
    return render_template("vendas.html", produtos=prods, vendas=recente)

@app.route("/vender", methods=["POST"])
@login_required
def vender():
    try:
        id_prod = int(request.form["id_produto"])
        qtd = int(request.form["quantidade"])
        
        p = produtos.buscar_produto_id(id_prod)
        if not p:
            flash("Produto não encontrado", "danger")
            return redirect("/vendas")

        ok, msg = vendas.vender_produto(id_prod, qtd, p[2], current_user.id)
        flash(msg, "success" if ok else "danger")
        if ok:
            registrar_log("VENDA", "VENDAS", f"Produto: {p[1]} | Qtd: {qtd}")
    except Exception as e:
        flash(f"Erro na venda: {str(e)}", "danger")
    return redirect("/vendas")

# ========================================================
# INICIALIZAÇÃO
# ========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)