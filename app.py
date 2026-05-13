import os
import json
import pandas as pd
import io
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, flash, abort, session
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import check_password_hash, generate_password_hash

# módulos
from modules import usuarios, vendas, estoque, produtos, receitas
from modules.permissoes import acesso_requerido
from modules.usuarios import registrar_log_db
from modules.db import conectar

# =========================
# APP
# =========================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "pupilos-confeitaria-senha-segura-2026")

# =========================
# LOGIN MANAGER
# =========================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# 1. Definição da Classe User (Essencial para o Flask-Login)
class User(UserMixin):
    def __init__(self, id_usuario, username, nivel):
        self.id = id_usuario  # O Flask-Login usa o atributo .id
        self.username = username
        self.nivel = nivel

@login_manager.user_loader
def load_user(id_usuario):
    # Recuperamos os dados que guardamos na sessão no momento do login
    nivel = session.get("nivel")
    username = session.get("username")
    if not id_usuario:
        return None
    return User(id_usuario, username, nivel)
# ========================================================
# TABELA LOGS (FIX ORDEM)
# ========================================================
with app.app_context():
    try:
        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                usuario TEXT,
                acao TEXT,
                modulo TEXT,
                detalhe TEXT,
                data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        cur.close()
        conn.close()

        print("✔ Logs verificados com sucesso")

    except Exception as e:
        print(f"Erro ao inicializar logs: {e}")

# ========================================================
# LOGS (CORRIGIDO)
# ========================================================
def registrar_log(acao, modulo, detalhe="", usuario_manual=None):
    usuario_log = usuario_manual or (current_user.id if current_user.is_authenticated else "anonimo")

    try:
        usuarios.registrar_log_db(usuario_log, acao, modulo, detalhe)
    except Exception as e:
        print(f"ERRO AO SALVAR LOG: {e}")


# =========================
# ROTAS DE AUTENTICAÇÃO
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username_form = request.form["username"].strip().lower()
        senha_form = request.form["senha"].strip()

        usuario = usuarios.buscar_usuario(username_form)

        if not usuario:
            flash("Usuário não encontrado", "danger")
            return render_template("login.html")

        # Mapeamento baseado no seu print:
        # usuario[0] = id_usuario, usuario[1] = username, usuario[3] = nivel
        id_user = usuario[0]
        username_db = usuario[1]
        senha_db = usuario[2]
        nivel_db = usuario[3]
        ativo = usuario[4]

        if ativo == 0:
            flash("Usuário bloqueado", "danger")
            return render_template("login.html")

        if not check_password_hash(senha_db, senha_form):
            flash("Senha incorreta", "danger")
            return render_template("login.html")

        # Criar objeto do usuário
        user_obj = User(id_user, username_db, nivel_db)
        login_user(user_obj)

        # GUARDAR NA SESSÃO (Isso é o que os decoradores verificam!)
        session["user_id"] = id_user
        session["nivel"] = nivel_db
        session["username"] = username_db

        registrar_log("LOGIN", "AUTH", f"Usuário {username_db} logado com sucesso")
        
        flash(f"Bem-vindo, {username_db}!", "success")
        return redirect("/")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    registrar_log("LOGOUT", "AUTH", f"{current_user.id} saiu")
    logout_user()
    session.clear()
    return redirect("/login")

# =========================
# DASHBOARD
# =========================
@app.route("/")
@login_required
def dashboard():
    try:
        # Busca dados reais do banco
        resumo_semanal = vendas.obter_resumo_periodo(7)
        resumo_mensal = vendas.obter_resumo_periodo(30)
        capacidade = produtos.calcular_capacidade_geral()
        insumos = estoque.listar_materia_prima()

        # Filtra itens críticos (estoque <= mínimo)
        criticos = [i for i in insumos if float(i[4]) <= float(i[3])]

        return render_template(
            "dashboard.html",
            semana=resumo_semanal,
            mes=resumo_mensal,
            capacidade=capacidade,
            criticos=criticos
        )
    except Exception as e:
        print(f"Erro no Dashboard: {e}")
        # Retorno de segurança para não quebrar a página
        return render_template(
            "dashboard.html",
            semana={"faturamento": 0, "vendas": 0},
            mes={"faturamento": 0, "vendas": 0},
            capacidade=0,
            criticos=[]
        )

# =========================
# ESTOQUE
# =========================
@app.route("/estoque")
@login_required
@acesso_requerido("estoque")
def estoque_page():
    return render_template("estoque.html", materias=estoque.listar_materia_prima())

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

# =========================
# VENDAS
# =========================
@app.route("/vendas")
@login_required
@acesso_requerido("vendas")
def vendas_page():
    return render_template("vendas.html", produtos=produtos.buscar_produto_por_nome(""))

@app.route("/vender", methods=["POST"])
@login_required
def vender():
    try:
        id_p = int(request.form["id_produto"])
        qtd = int(request.form["quantidade"])

        prods = produtos.buscar_produto_por_nome("")
        produto = next((p for p in prods if p[0] == id_p), None)

        if not produto:
            flash("Produto não encontrado", "danger")
            return redirect("/vendas")

        sucesso, msg = vendas.vender_produto(id_p, qtd, produto[2])

        if sucesso:
            registrar_log("VENDA", "VENDAS", f"ID {id_p} | Qtd {qtd}")
            flash(msg, "success")
        else:
            flash(msg, "danger")
    except Exception as e:
        flash(f"Erro ao vender: {e}", "danger")
    return redirect("/vendas")

# =========================
# FINANCEIRO E AUDITORIA
# =========================
@app.route("/financeiro")
@login_required
@acesso_requerido("financeiro")
def pagina_financeiro():
    try:
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
    except Exception as e:
        flash("Erro ao carregar dados financeiros", "warning")
        return redirect("/")

@app.route("/auditoria")
@login_required
@acesso_requerido("auditoria")
def auditoria():
    logs_data = usuarios.listar_logs_auditoria(100)
    return render_template('auditoria.html', logs=logs_data)

# =========================
# GESTÃO DE USUÁRIOS
# =========================
@app.route("/usuarios")
@login_required
@acesso_requerido("usuarios")
def usuarios_page():
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
        novo_status = 0 if user_db[4] == 1 else 1
        usuarios.alterar_status(id_usuario, novo_status)
        flash("Status alterado!", "success")
    return redirect("/usuarios")

# =========================
# IMPORTAÇÕES
# =========================
@app.route("/importacoes")
@login_required
def central_importacoes():
    return render_template("central_importacoes.html")

@app.route("/importar-ifood", methods=["POST"])
@login_required
def importar_ifood():
    arquivo = request.files.get("arquivo")
    if arquivo:
        registrar_log("IMPORT_IFOOD", "VENDAS", f"Arquivo: {arquivo.filename}")
        flash("Processamento de iFood iniciado!", "info")
    return redirect("/importacoes")

# =========================
# INICIALIZAÇÃO
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)