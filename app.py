import os
import json
import pandas as pd
import io
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
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
        self.id = id_usuario  # O Flask-Login usa 'id' por padrão
        self.username = username
        self.nivel = nivel

@login_manager.user_loader
def load_user(id_usuario):
    # Recuperamos o nível e o nome da sessão para manter o objeto User completo
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

        # Chama sua função que busca no banco
        usuario = usuarios.buscar_usuario(username_form)

        if not usuario:
            flash("Usuário não encontrado", "danger")
            return render_template("login.html")

        # MAPEAMENTO CORRETO DO SEU PRINT:
        id_user = usuario[0]    # 1 ou 4
        username_db = usuario[1] # 'admin' ou 'amanda'
        senha_db = usuario[2]    # o hash scrypt...
        nivel_db = usuario[3]    # 'admin'
        ativo = usuario[4]       # 1

        if ativo == 0:
            flash("Usuário bloqueado", "danger")
            return render_template("login.html")

        if not check_password_hash(senha_db, senha_form):
            flash("Senha incorreta", "danger")
            return render_template("login.html")

        # Criar o objeto User com o nível do banco
        user_obj = User(id_user, username_db, nivel_db)
        login_user(user_obj)

        # SALVAR NA SESSÃO (Isso aqui é o que destrava o acesso!)
        session["user_id"] = id_user
        session["nivel"] = nivel_db
        session["username"] = username_db

        registrar_log("LOGIN", "AUTH", f"Usuário {username_db} logou com sucesso")
        
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


@app.route("/usuarios/excluir/<int:id>", methods=["POST"])
@login_required
@acesso_requerido("admin") # Garante que só admin deleta
def deletar_user(id):
    if usuarios.excluir_usuario(id):
        flash("Usuário removido com sucesso!", "success")
    else:
        flash("Erro ao tentar remover usuário.", "danger")
    
    return redirect("/usuarios")

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


# --- ROTA PRINCIPAL DA CENTRAL DE CADASTROS ---
@app.route("/cadastro")
@login_required
def render_cadastro():
    # Carrega dados para preencher os selects da Ficha Técnica (Engenharia de Produto)
    try:
        lista_produtos = produtos.listar_todos() 
        lista_materias = materias.listar_todas()
        return render_template("cadastro.html", produtos=lista_produtos, materias=lista_materias)
    except Exception as e:
        flash(f"Erro ao carregar dados: {e}", "danger")
        return redirect(url_for('index'))

# --- AÇÃO: CADASTRAR MATÉRIA-PRIMA (INSUMOS) ---
@app.route("/cadastrar-mp", methods=["POST"])
@login_required
def cadastrar_mp():
    nome = request.form.get("nome")
    unidade = request.form.get("unidade")
    estoque_at = request.form.get("estoque_atual")
    preco = request.form.get("preco")
    estoque_min = request.form.get("estoque_minimo")
    
    # Chama a função do seu módulo materias.py
    # Ajuste os argumentos conforme sua função original aceita
    if materias.cadastrar_materia(nome, unidade, preco, estoque_at, estoque_min):
        flash(f"Insumo '{nome}' salvo no PostgreSQL!", "success")
    else:
        flash("Erro técnico ao salvar insumo.", "danger")
    
    return redirect(url_for('render_cadastro'))

# --- AÇÃO: CADASTRAR PRODUTO FINAL ---
@app.route("/cadastrar-produto", methods=["POST"])
@login_required
def cadastrar_produto_final():
    nome = request.form.get("nome")
    preco = request.form.get("preco")
    categoria = request.form.get("categoria")
    
    if produtos.cadastrar_produto(nome, preco, categoria):
        flash(f"Produto '{nome}' cadastrado com sucesso!", "success")
    else:
        flash("Erro ao cadastrar produto final.", "danger")
        
    return redirect(url_for('render_cadastro'))

# --- AÇÃO: VINCULAR RECEITA (ENGENHARIA) ---
@app.route("/vincular-receita", methods=["POST"])
@login_required
def vincular_receita():
    id_produto = request.form.get("id_produto")
    id_materia = request.form.get("id_materia_prima")
    quantidade = request.form.get("quantidade")
    
    # Aqui chama a função que cria o vínculo na tabela de receitas/fichas técnicas
    if produtos.vincular_insumo(id_produto, id_materia, quantidade):
        flash("Ingrediente vinculado ao produto!", "success")
    else:
        flash("Erro ao vincular ingrediente.", "danger")
        
    return redirect(url_for('render_cadastro'))


# --- ROTA: EXCLUIR PRODUTO ---
@app.route("/excluir-produto/<int:id_produto>")
@login_required
def deletar_produto(id_produto):
    if session.get("nivel") not in ["admin", "gerente"]:
        flash("Acesso negado! Apenas Gerentes podem excluir produtos.", "danger")
        return redirect(url_for('listar_estoque')) # Ajuste para sua rota de estoque

    try:
        usuarios.excluir_produto(id_produto)
        # Registrar na auditoria que você já tem pronta
        registrar_log(session.get('user'), "EXCLUIR", "ESTOQUE", f"Removeu produto ID {id_produto}")
        flash("Produto removido com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao excluir: {e}", "danger")
    
    return redirect(url_for('listar_estoque'))

# --- ROTA: EXCLUIR MATÉRIA-PRIMA ---
@app.route("/excluir-mp/<int:id_mp>")
@login_required
def deletar_mp(id_mp):
    if session.get("nivel") not in ["admin", "gerente"]:
        flash("Permissão insuficiente.", "danger")
        return redirect(url_for('listar_estoque'))

    try:
        usuarios.excluir_materia_prima(id_mp)
        registrar_log(session.get('user'), "EXCLUIR", "MATERIA_PRIMA", f"Removeu insumo ID {id_mp}")
        flash("Matéria-prima removida!", "info")
    except Exception as e:
        flash(f"Erro ao excluir: {e}", "danger")
        
    return redirect(url_for('listar_estoque'))

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

# --- ROTA: TELA DE AUDITORIA ---
@app.route("/auditoria")
@login_required
def auditoria():
    # Segurança em duas camadas: Decorator + Verificação de Nível
    if session.get("nivel") != "admin":
        flash("Acesso restrito! Somente administradores podem ver a auditoria.", "danger")
        return redirect(url_for('index'))
    
    try:
        # Busca os últimos 100 logs
        logs_data = usuarios.listar_logs_auditoria(100)
        return render_template('auditoria.html', logs=logs_data)
    except Exception as e:
        flash(f"Erro ao carregar logs: {e}", "danger")
        return redirect(url_for('index'))

# --- ROTA: EXPORTAR LOGS (Para o botão do HTML funcionar) ---
@app.route("/logs/exportar")
@login_required
def exportar_logs():
    if session.get("nivel") != "admin":
        abort(403)
        
    logs_data = usuarios.listar_logs_auditoria(500) # Exporta mais logs para o arquivo
    
    # Converte os dados para JSON formatado
    json_output = json.dumps(logs_data, indent=4, default=str)
    
    return Response(
        json_output,
        mimetype="application/json",
        headers={"Content-disposition": "attachment; filename=auditoria_agatha_erp.json"}
    )
# =========================
# GESTÃO DE USUÁRIOS & EQUIPE
# =========================

# --- ROTA: LISTAR EQUIPE (Acesso: Admin e Gerente) ---
@app.route("/usuarios")
@login_required
def listar_usuarios():
    # Bloqueio de segurança: Se não for admin ou gerente, volta para a index
    if session.get("nivel") not in ["admin", "gerente"]:
        flash("Acesso negado! Área exclusiva para Gerência ou Admin.", "danger")
        return redirect(url_for('index'))
    
    # Busca a lista de usuários no banco (PostgreSQL)
    try:
        lista = usuarios.listar_todos() 
        return render_template("usuarios.html", equipe=lista)
    except Exception as e:
        flash(f"Erro ao carregar equipe: {e}", "danger")
        return redirect(url_for('index'))

# --- ROTA: CRIAR USUÁRIO (Acesso: APENAS Admin) ---
@app.route("/criar-usuario", methods=["POST"])
@login_required
def criar_usuario():
    # Trava de segurança: Apenas Admin pode criar novos perfis
    if session.get("nivel") != "admin":
        flash("Apenas Administradores podem criar novos usuários.", "danger")
        return redirect(url_for('listar_usuarios'))

    user = request.form.get("username").strip().lower()
    passw = request.form.get("senha").strip()
    nivel = request.form.get("nivel") # admin, gerente, vendedor, etc.
    
    if len(passw) < 6:
        flash("A senha deve ter no mínimo 6 caracteres!", "warning")
    else:
        try:
            hash_senha = generate_password_hash(passw)
            if usuarios.criar_usuario(user, hash_senha, nivel):
                # registrar_log é opcional, caso você tenha essa função de auditoria
                # registrar_log("CRIAR_USER", "USUARIOS", f"Criou {user}")
                flash(f"Usuário '{user}' criado com sucesso!", "success")
            else:
                flash("Erro ao salvar no banco. Verifique se o login já existe.", "danger")
        except Exception as e:
            flash(f"Erro técnico: {e}", "danger")

    return redirect(url_for('listar_usuarios'))

# --- ROTA: ATIVAR/DESATIVAR USUÁRIO (Acesso: APENAS Admin) ---
@app.route("/toggle-usuario/<int:id_usuario>")
@login_required
def toggle_usuario(id_usuario):
    # Trava de segurança: Gerentes vêem a lista, mas só Admin desativa pessoas
    if session.get("nivel") != "admin":
        flash("Permissão insuficiente para alterar status de usuários.", "danger")
        return redirect(url_for('listar_usuarios'))

    try:
        user_db = usuarios.buscar_usuario_id(id_usuario)
        if user_db:
            # Assume-se que o status está na coluna índice 4 (ajuste conforme seu banco)
            # Se status for 1 (ativo), vira 0 (inativo) e vice-versa
            novo_status = 0 if user_db[4] == 1 else 1
            usuarios.alterar_status(id_usuario, novo_status)
            
            status_txt = "Ativado" if novo_status == 1 else "Desativado"
            flash(f"Usuário {user_db[1]} foi {status_txt}!", "info")
        else:
            flash("Usuário não encontrado.", "warning")
    except Exception as e:
        flash(f"Erro ao alterar status: {e}", "danger")

    return redirect(url_for('listar_usuarios'))

# --- ROTA: PAINEL DE CONFIGURAÇÃO (Acesso: APENAS Admin) ---
@app.route("/admin/config")
@login_required
def area_admin():
    if session.get("nivel") != "admin":
        abort(403) 
    return render_template("admin_panel.html") # <--- Este nome

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