
import io
import os
import csv
import json
import uuid
import tempfile
 
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from flask import (
    Flask, Response, abort, flash, jsonify, make_response,
    redirect, render_template, request, send_file, session, url_for,
)
from flask_login import (
    LoginManager, UserMixin, current_user, login_required,
    login_user, logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash
from google import genai
from datetime import datetime
 
# --- módulos internos (sem wildcard) ---
from modules import usuarios, vendas, estoque, produtos, receitas
from modules.db import get_conn
from modules.auth import load_user as _load_user
from modules.ocr_notas import analisar_nota, limpar_e_parsear_json
from modules.permissoes import acesso_requerido
from modules.importador_ia import (
    ler_arquivo,
    interpretar_relatorio_com_ia,
    normalizar_vendas,
    salvar_vendas,
    gerar_financeiro,
    localizar_produto_erp,
    baixar_estoque_delivery,
    processar_relatorio_delivery,
)
from modules.financeiro import (
    financeiro_operacional,
    calcular_financeiro_com_imposto,
    get_config_empresa,
    calcular_imposto,
    relatorio_fiscal,
)
from utils.logger import log_info, log_erro
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from PIL import Image

 
# =============================================================
#APP
# =============================================================
client = genai.Client()
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.secret_key = os.getenv("SECRET_KEY", "6ba4d0522eae6dd5b8cab367aefee7e306c0d9196a9e91507c1591ed615189b2")
 
# =============================================================
# LOGIN MANAGER
# =============================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

 
 
class User(UserMixin):
    def __init__(self, id_usuario, username, nivel):
        self.id = id_usuario
        self.username = username
        self.nivel = nivel
# =============================================================
# RATE LIMIT
# =============================================================

def get_rate_limit_key():
    try:
        if current_user.is_authenticated:
            return f"user:{current_user.id}"
    except Exception:
        pass

    return get_remote_address()


limiter = Limiter(
    key_func=lambda: current_user.id if current_user.is_authenticated else get_remote_address(),
    app=app,
    default_limits=["200 per day", "50 per hour"]
)
 
 
@login_manager.user_loader
def load_user(user_id):
    """
    Carrega o usuário do banco a cada request autenticado.
    Não depende da session — evita estados inconsistentes.
    """
    return _load_user(user_id)
 
 
# =============================================================
# INICIALIZAÇÃO DA TABELA DE LOGS
# =============================================================
with app.app_context():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id SERIAL PRIMARY KEY,
                        usuario TEXT,
                        acao TEXT,
                        modulo TEXT,
                        detalhe TEXT,
                        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()
        print("✔ Tabela de logs verificada.")
    except Exception as e:
        print(f"❌ Erro ao inicializar tabela de logs: {e}")
 
 
# =============================================================
# UTILITÁRIO DE LOG
# =============================================================
def registrar_log(acao: str, modulo: str, detalhe: str = "") -> None:
    try:
        usuario_atual = "Sistema"
        if current_user.is_authenticated:
            usuario_atual = getattr(current_user, "username", "Desconhecido")
        elif session.get("username"):
            usuario_atual = session["username"]
 
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO logs (usuario, acao, modulo, detalhe) VALUES (%s,%s,%s,%s)",
                    (usuario_atual, acao, modulo, detalhe),
                )
            conn.commit()
    except Exception as e:
        log_erro(f"Falha ao gravar log: {e}")
 
 
def _parse_float(valor: str, default: float = 0.0) -> float:
    """Converte string de formulário para float de forma segura."""
    try:
        return float(str(valor).replace(",", ".").strip())
    except (ValueError, TypeError):
        return default
 
 
# =============================================================
# AUTENTICAÇÃO
# =============================================================
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        username_form = request.form.get("username", "").strip().lower()
        senha_form = request.form.get("senha", "").strip()
 
        usuario = usuarios.buscar_usuario(username_form)
        if not usuario:
            flash("Usuário ou senha inválidos.", "danger")
            return render_template("login.html"), 401
 
        try:
            id_user, username_db, senha_db, nivel_db, ativo = usuario[:5]
        except (ValueError, TypeError):
            flash("Erro interno no sistema de autenticação.", "danger")
            return render_template("login.html"), 500
 
        if int(ativo) == 0:
            flash("Usuário ou senha inválidos.", "danger")
            return render_template("login.html"), 403
 
        if not check_password_hash(senha_db, senha_form):
            flash("Usuário ou senha incorretos.", "danger")
            return render_template("login.html"), 401
 
        user_obj = User(id_user, username_db, nivel_db)
        session.clear()
        login_user(user_obj)
        session["user_id"] = id_user
        session["nivel"] = nivel_db
        session["username"] = username_db
 
        registrar_log("LOGIN", "AUTH", f"Usuário '{username_db}' autenticado")
        flash(f"Bem-vindo de volta, {username_db}!", "success")
        return redirect(url_for("dashboard"))
 
    return render_template("login.html")
 
 
@app.route("/logout")
@login_required
def logout():
    registrar_log("LOGOUT", "AUTH", f"Usuário '{current_user.username}' saiu")
    logout_user()
    session.clear()
    return redirect("/login")
 
 
# =============================================================
# DASHBOARD
# =============================================================
@app.route("/")
@login_required
def dashboard():
    valores_vazios = {"faturamento": 0, "total_vendas": 0, "lucro": 0}
    try:
        resumo_diario  = vendas.obter_resumo_periodo(1)  or valores_vazios
        resumo_semanal = vendas.obter_resumo_periodo(7)  or valores_vazios
        resumo_mensal  = vendas.obter_resumo_periodo(30) or valores_vazios
        capacidade = produtos.calcular_capacidade_geral()
 
        insumos = estoque.listar_materia_prima() or []
        criticos = [
            item for item in insumos
            if float(item[4] or 0) <= float(item[3] or 0)
        ]
 
        return render_template(
            "dashboard.html",
            diario=resumo_diario,
            semana=resumo_semanal,
            mes=resumo_mensal,
            capacidade=capacidade,
            criticos=criticos,
        )
    except Exception as e:
        log_erro(f"Erro no dashboard: {e}")
        return render_template(
            "dashboard.html",
            diario=valores_vazios, semana=valores_vazios, mes=valores_vazios,
            capacidade=[], criticos=[],
        )
 
 
# =============================================================
# ESTOQUE — PAINEL PRINCIPAL
# =============================================================
@app.route("/estoque", methods=["GET"])
@login_required
def estoque_painel():
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT
                        m.id_materia_prima, m.nome, m.unidade_medida, m.estoque_minimo,
                        COALESCE(SUM(CASE WHEN mov.tipo_movimento IN ('entrada','ajuste')
                                         THEN mov.quantidade ELSE 0 END), 0)
                        - COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'saida'
                                           THEN mov.quantidade ELSE 0 END), 0) AS estoque_atual,
                        CASE WHEN (
                            COALESCE(SUM(CASE WHEN mov.tipo_movimento IN ('entrada','ajuste')
                                             THEN mov.quantidade ELSE 0 END), 0)
                            - COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'saida'
                                               THEN mov.quantidade ELSE 0 END), 0)
                        ) <= m.estoque_minimo THEN 'BAIXO' ELSE 'OK' END AS status,
                        COALESCE(m.preco_unitario, 0),
                        TO_CHAR(m.data_cadastro, 'DD/MM/YYYY')
                    FROM materia_prima m
                    LEFT JOIN movimentacao_estoque mov ON m.id_materia_prima = mov.id_materia_prima
                    GROUP BY m.id_materia_prima, m.nome, m.unidade_medida,
                             m.estoque_minimo, m.preco_unitario, m.data_cadastro
                    ORDER BY m.nome ASC
                """)
                materias = cur.fetchall()
 
                cur.execute("""
                    SELECT id_subproduto, nome, 0, preco_custo_unidade,
                           unidade_medida, TO_CHAR(data_cadastro, 'DD/MM/YYYY')
                    FROM subprodutos ORDER BY nome ASC
                """)
                subprodutos = cur.fetchall()
 
                cur.execute("""
                    SELECT id_produto, nome, preco_venda, categoria, 0,
                           TO_CHAR(data_cadastro, 'DD/MM/YYYY')
                    FROM produtos ORDER BY nome ASC
                """)
                lista_produtos = cur.fetchall()
 
        return render_template(
            "estoque.html",
            materias=materias, subprodutos=subprodutos, produtos=lista_produtos,
        )
    except Exception as e:
        log_erro(f"Erro no painel de estoque: {e}")
        flash(f"Não foi possível carregar o painel de estoque: {e}", "danger")
        return redirect("/")
 
 
@app.route("/compras")
@login_required
def pagina_compras():
    return render_template("compras.html", materias=estoque.listar_materia_prima())
 
 
@app.route("/registrar-producao", methods=["POST"])
@login_required
@acesso_requerido("estoque")
def registrar_producao():
    try:
        tipo_item   = request.form.get("tipo_item", "")
        id_item_raw = request.form.get("id_item", "")
        qtd_raw     = request.form.get("quantidade", "").strip()
 
        if not id_item_raw or not id_item_raw.isdigit():
            flash("ID do item inválido.", "danger")
            return redirect("/estoque")
 
        id_item = int(id_item_raw)
        qtd = _parse_float(qtd_raw)
 
        if qtd <= 0:
            flash("A quantidade deve ser maior que zero.", "warning")
            return redirect("/estoque")
 
        if tipo_item == "subproduto":
            estoque.entrada_subproduto(id_item, qtd)
            registrar_log("PRODUCAO", "SUBPRODUTO", f"ID {id_item} | Qtd {qtd}")
        elif tipo_item == "produto":
            estoque.entrada_produto(id_item, qtd)
            registrar_log("PRODUCAO", "PRODUTO", f"ID {id_item} | Qtd {qtd}")
        else:
            flash("Tipo de item desconhecido.", "danger")
            return redirect("/estoque")
 
        flash(f"Produção de {qtd} unidade(s) registrada com sucesso!", "success")
    except Exception as e:
        log_erro(f"Erro ao registrar produção: {e}")
        flash(f"Erro ao processar produção: {e}", "danger")
 
    return redirect("/estoque")
 
 
@app.route("/estoque/balanco-diario")
@login_required
@acesso_requerido("estoque")
def balanco_diario_page():
    try:
        data_param = request.args.get("data", "").strip()
        if data_param:
            hoje_str = data_param
            try:
                ano, mes, dia = hoje_str.split("-")
                data_exibicao = f"{dia}/{mes}/{ano}"
            except ValueError:
                data_exibicao = hoje_str
        else:
            hoje_str = datetime.now().strftime("%Y-%m-%d")
            data_exibicao = datetime.now().strftime("%d/%m/%Y")
 
        lista_produtos = produtos.listar_todos() or []
 
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT iv.id_produto, DATE(v.data_venda), SUM(iv.quantidade)
                    FROM itens_venda iv
                    JOIN vendas v ON v.id_venda = iv.id_venda
                    WHERE DATE(v.data_venda) = %s
                    GROUP BY iv.id_produto, DATE(v.data_venda)
                """, (hoje_str,))
                vendas_do_dia = {str(r[0]): int(r[2]) for r in cur.fetchall()}
 
        balanco = []
        for p in lista_produtos:
            id_produto, nome_produto = p[0], p[1]
            vendido_hoje = vendas_do_dia.get(str(id_produto), 0)
            balanco.append({
                "id": id_produto,
                "nome": nome_produto,
                "vendido": vendido_hoje,
            })
 
        return render_template(
            "balanco_diario.html",
            data_hoje=data_exibicao,
            data_busca_atual=hoje_str,
            datetime_hoje=datetime.now().strftime("%Y-%m-%d"),
            balanco=balanco,
        )
    except Exception as e:
        log_erro(f"Erro no balanço diário: {e}")
        flash(f"Erro ao processar balanço diário: {e}", "danger")
        return redirect(url_for("estoque_painel"))
 
 
@app.route("/estoque/fechamento")
@login_required
@acesso_requerido("estoque")
def fechamento_diario():
    dados_fechamento = estoque.obter_balanco_diario()
    return render_template("fechamento.html", balanco=dados_fechamento)
 
 
# =============================================================
# ESTOQUE — EDIÇÃO E EXCLUSÃO
# =============================================================
@app.route("/editar-produto/<int:id_produto>", methods=["POST"])
@login_required
def atualizar_produto(id_produto):
    nome = request.form.get("nome", "").strip()
    preco_raw = request.form.get("preco", "0").strip()
 
    if not nome:
        flash("O nome não pode ficar em branco.", "warning")
        return redirect(url_for("estoque_painel"))
 
    preco = _parse_float(preco_raw)
    if preco < 0:
        flash("Preço inválido.", "danger")
        return redirect(url_for("estoque_painel"))
 
    if produtos.update_produto(id_produto, nome, preco):
        registrar_log("ALTERAR", "PRODUTOS", f"ID {id_produto} → {nome} | R$ {preco}")
        flash("Produto atualizado!", "success")
    else:
        flash("Erro ao atualizar produto.", "danger")
 
    return redirect(url_for("estoque_painel"))
 
 
@app.route("/editar-materia-prima/<int:id_mp>", methods=["POST"])
@login_required
def processar_edicao_mp(id_mp):
    nome     = request.form.get("nome", "").strip()
    unidade  = request.form.get("unidade", "").strip()
    preco    = _parse_float(request.form.get("preco_custo", "0"))
    qtd      = _parse_float(request.form.get("quantidade", "0"))
 
    if not nome or not unidade:
        flash("Nome e Unidade são obrigatórios.", "warning")
        return redirect(url_for("estoque_painel"))
 
    if preco < 0 or qtd < 0:
        flash("Valores numéricos inválidos.", "danger")
        return redirect(url_for("estoque_painel"))
 
    if estoque.atualizar_materia_prima(id_mp, nome, preco, unidade, qtd):
        registrar_log("ALTERAR", "MATERIA_PRIMA", f"ID {id_mp} → {nome} | Qtd {qtd}")
        flash("Matéria-prima atualizada!", "success")
    else:
        flash("Erro ao atualizar matéria-prima.", "danger")
 
    return redirect(url_for("estoque_painel"))
 
 
@app.route("/excluir-produto/<int:id_produto>", methods=["POST"])
@login_required
@acesso_requerido("estoque")
def deletar_produto(id_produto):
    if produtos.excluir_produto(id_produto):
        registrar_log("DELETAR", "PRODUTOS", f"ID {id_produto} removido por '{current_user.username}'")
        flash("Produto excluído!", "success")
    else:
        flash("Não foi possível excluir o produto.", "warning")
    return redirect(url_for("estoque_painel"))
 
 
@app.route("/excluir-mp/<int:id_mp>", methods=["POST"])
@login_required
@acesso_requerido("estoque")
def deletar_mp(id_mp):
    if estoque.excluir_materia_prima(id_mp):
        registrar_log("DELETAR", "MATERIA_PRIMA", f"ID {id_mp} removido por '{current_user.username}'")
        flash("Matéria-prima excluída!", "success")
    else:
        flash("Não foi possível remover o insumo.", "warning")
    return redirect(url_for("estoque_painel"))
 
 
# =============================================================
# CADASTRO CENTRAL
# =============================================================
@app.route("/cadastro")
@login_required
def render_cadastro():
    try:
        return render_template(
            "cadastro.html",
            produtos=produtos.listar_todos() or [],
            materias=estoque.listar_materia_prima() or [],
            subprodutos=estoque.listar_subprodutos() or [],
        )
    except Exception as e:
        log_erro(f"Erro ao renderizar cadastro: {e}")
        flash("Erro ao carregar a central de cadastros.", "danger")
        return redirect(url_for("dashboard"))
 
 
@app.route("/cadastrar-mp", methods=["POST"])
@login_required
def cadastrar_mp():
    nome    = request.form.get("nome", "").strip()
    unidade = request.form.get("unidade", "").strip()
    preco   = _parse_float(request.form.get("preco", ""))
    est_at  = _parse_float(request.form.get("estoque_atual", "0"))
    est_min = _parse_float(request.form.get("estoque_minimo", "0"))
 
    if not nome or not unidade or preco <= 0:
        flash("Nome, Unidade e Preço são obrigatórios.", "warning")
        return redirect(url_for("render_cadastro"))
 
    if estoque.cadastrar_materia(nome, unidade, preco, est_at, est_min):
        registrar_log("CADASTRO", "MATERIA_PRIMA", f"{nome} | R$ {preco}")
        flash(f"Insumo '{nome}' salvo!", "success")
    else:
        flash("Erro ao salvar insumo.", "danger")
 
    return redirect(url_for("render_cadastro"))
 
 
@app.route("/cadastrar-produto", methods=["POST"])
@login_required
def cadastrar_produto_final():
    nome      = request.form.get("nome", "").strip()
    preco     = _parse_float(request.form.get("preco", ""))
    categoria = request.form.get("categoria", "").strip()
 
    if not nome or preco <= 0:
        flash("Nome e Preço são obrigatórios.", "warning")
        return redirect(url_for("render_cadastro"))
 
    if produtos.cadastrar_produto(nome, preco, categoria):
        registrar_log("CADASTRO", "PRODUTO", f"{nome} | R$ {preco}")
        flash(f"Produto '{nome}' cadastrado!", "success")
    else:
        flash("Erro ao salvar produto.", "danger")
 
    return redirect(url_for("render_cadastro"))
 
 
@app.route("/vincular-receita", methods=["POST"])
@login_required
def vincular_receita():
    id_p = request.form.get("id_produto")
    id_m = request.form.get("id_materia_prima")
    qtd  = _parse_float(request.form.get("quantidade", "0"))
 
    if not id_p or not id_m or qtd <= 0:
        flash("Selecione produto, insumo e informe quantidade > 0.", "warning")
        return redirect(url_for("render_cadastro"))
 
    if produtos.vincular_insumo(id_p, id_m, qtd):
        registrar_log("CADASTRO", "FICHA_TECNICA", f"MP {id_m} → Prod {id_p} | Qtd {qtd}")
        flash("Ingrediente vinculado!", "success")
    else:
        flash("Erro ao vincular ingrediente.", "danger")
 
    return redirect(url_for("render_cadastro"))
 
 
@app.route("/cadastrar-subproduto", methods=["POST"])
@login_required
def cadastrar_subproduto():
    nome      = request.form.get("nome", "").strip()
    unidade   = request.form.get("unidade", "").strip()
    est_min   = _parse_float(request.form.get("estoque_minimo", "0"))
 
    if not nome or not unidade:
        flash("Nome e Unidade são obrigatórios.", "warning")
        return redirect(url_for("render_cadastro"))
 
    if estoque.cadastrar_subproduto_banco(nome, unidade, est_min):
        registrar_log("CADASTRO", "SUBPRODUTO", f"Novo subproduto: {nome}")
        flash(f"Subproduto '{nome}' cadastrado!", "success")
    else:
        flash("Erro ao cadastrar subproduto.", "danger")
 
    return redirect(url_for("render_cadastro"))
 
 
@app.route("/vincular-receita-subproduto", methods=["POST"])
@login_required
def vincular_receita_subproduto():
    id_sub = request.form.get("id_subproduto")
    id_m   = request.form.get("id_materia_prima")
    qtd    = _parse_float(request.form.get("quantidade", "0"))
 
    if not id_sub or not id_m or qtd <= 0:
        flash("Dados incompletos.", "warning")
        return redirect(url_for("render_cadastro"))
 
    if estoque.vincular_insumo_subproduto(id_sub, id_m, qtd):
        flash("Ingrediente vinculado ao subproduto!", "success")
    else:
        flash("Erro ao vincular.", "danger")
 
    return redirect(url_for("render_cadastro"))
 
 
@app.route("/vincular-subproduto-produto", methods=["POST"])
@login_required
def vincular_subproduto_produto():
    id_p   = request.form.get("id_produto")
    id_sub = request.form.get("id_subproduto")
    qtd    = _parse_float(request.form.get("quantidade", "0"))
 
    if not id_p or not id_sub or qtd <= 0:
        flash("Dados incompletos.", "warning")
        return redirect(url_for("render_cadastro"))
 
    if produtos.vincular_subproduto_ao_produto(id_p, id_sub, qtd):
        flash("Subproduto vinculado ao produto!", "success")
    else:
        flash("Erro ao vincular.", "danger")
 
    return redirect(url_for("render_cadastro"))
 
 
@app.route("/excluir-subproduto/<int:id_subproduto>")
@login_required
@acesso_requerido("estoque")
def deletar_subproduto(id_subproduto):
    if estoque.excluir_subproduto_banco(id_subproduto):
        registrar_log("EXCLUIR", "SUBPRODUTO", f"ID {id_subproduto}")
        flash("Subproduto removido!", "success")
    else:
        flash("Erro ao excluir subproduto.", "danger")
    return redirect(url_for("estoque_painel"))
 
 
@app.route("/cadastro-central")
@login_required
def cadastro_central():
    return redirect(url_for("estoque_painel"))
 
 
# =============================================================
# PRECIFICAÇÃO
# =============================================================
@app.route("/precificacao")
@login_required
def precificacao():
    try:
        with get_conn() as con:
            with con.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.id_produto, p.nome, p.preco_venda,
                           COALESCE(SUM(r.quantidade_utilizada * mp.preco_unitario), 0) AS custo_producao
                    FROM produtos p
                    LEFT JOIN receitas r ON p.id_produto = r.id_produto
                    LEFT JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
                    WHERE p.ativo = 1
                    GROUP BY p.id_produto, p.nome, p.preco_venda
                    ORDER BY p.nome ASC
                """)
                produtos_db = cur.fetchall()
 
        tabela = []
        for p in produtos_db:
            custo = float(p["custo_producao"])
            venda = float(p["preco_venda"])
            tabela.append({
                "id": p["id_produto"],
                "nome": p["nome"],
                "atual": venda,
                "custo": custo,
                "equilibrio": custo * 1.10,
                "sugerido": custo / 0.7 if custo > 0 else 0,
                "alerta": venda < (custo * 1.10) if custo > 0 else False,
            })
 
        return render_template("precificacao.html", tabela=tabela)
    except Exception as e:
        log_erro(f"Erro na precificação: {e}")
        flash(f"Erro ao carregar precificação: {e}", "danger")
        return redirect("/")
 
 
# =============================================================
# FICHA TÉCNICA
# =============================================================
@app.route("/ficha-tecnica/<int:id_produto>")
@login_required
def ficha_tecnica(id_produto):
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    "SELECT id_produto, nome, preco_venda FROM produtos WHERE id_produto = %s",
                    (id_produto,),
                )
                produto = cur.fetchone()
                if not produto:
                    flash("Produto não encontrado.", "danger")
                    return redirect(url_for("estoque_painel"))
 
                cur.execute("""
                    SELECT r.id_receita, 'materia_prima', mp.id_materia_prima, mp.nome,
                           r.quantidade_utilizada, mp.unidade_medida,
                           r.quantidade_utilizada * COALESCE(mp.preco_unitario, 0)
                    FROM receitas r
                    JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
                    WHERE r.id_produto = %s AND r.id_subproduto IS NULL
 
                    UNION ALL
 
                    SELECT r.id_receita, 'subproduto', sub.id_subproduto, sub.nome,
                           r.quantidade_utilizada, sub.unidade_medida,
                           r.quantidade_utilizada * COALESCE(sub.preco_custo_unidade, 0)
                    FROM receitas r
                    JOIN subprodutos sub ON r.id_subproduto = sub.id_subproduto
                    WHERE r.id_produto = %s AND r.id_subproduto IS NOT NULL
                """, (id_produto, id_produto))
 
                colunas = [d[0] for d in cur.description]
                itens = [dict(zip(colunas, row)) for row in cur.fetchall()]
 
        total_custo = sum(float(i.get("custo_subtotal") or i.get(colunas[6], 0)) for i in itens)
        preco_venda = float(produto[2] or 0)
        lucro = preco_venda - total_custo
        margem = (lucro / preco_venda * 100) if preco_venda > 0 else 0
 
        return render_template(
            "ficha_tecnica.html",
            produto=[produto[0], produto[1], preco_venda],
            itens=itens,
            total=round(total_custo, 2),
            lucro=round(lucro, 2),
            margem=round(margem, 2),
        )
    except Exception as e:
        log_erro(f"Erro na ficha técnica ID {id_produto}: {e}")
        flash(f"Erro ao processar ficha técnica: {e}", "danger")
        return redirect(url_for("estoque_painel"))
 
 
@app.route("/ficha-tecnica/editar-item/<int:id_produto>", methods=["POST"])
@login_required
def editar_item_ficha(id_produto):
    id_vinculo_raw = request.form.get("id_vinculo")
    qtd_raw = request.form.get("quantidade", "0").strip()
 
    if not id_vinculo_raw:
        flash("Vínculo inválido.", "warning")
        return redirect(f"/ficha-tecnica/{id_produto}")
 
    try:
        id_vinculo = int(id_vinculo_raw)
        nova_qtd = _parse_float(qtd_raw)
        if nova_qtd < 0:
            raise ValueError
    except ValueError:
        flash("Quantidade deve ser um número positivo.", "danger")
        return redirect(f"/ficha-tecnica/{id_produto}")
 
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    "UPDATE receitas SET quantidade_utilizada = %s WHERE id_receita = %s AND id_produto = %s",
                    (nova_qtd, id_vinculo, id_produto),
                )
            con.commit()
        registrar_log("ALTERAR", "FICHA_TECNICA", f"Vínculo {id_vinculo} → {nova_qtd}")
        flash("Quantidade ajustada!", "success")
    except Exception as e:
        log_erro(f"Erro ao editar ficha técnica: {e}")
        flash(f"Erro ao salvar: {e}", "danger")
 
    return redirect(f"/ficha-tecnica/{id_produto}")
 
 
# =============================================================
# LOTES E AJUSTE DE PREÇOS
# =============================================================
@app.route("/subprodutos/registrar-lote", methods=["POST"])
@login_required
def registrar_lote():
    nome_comercial   = request.form.get("nome", "").strip()
    preco_venda_raw  = request.form.get("preco", "").strip()
    id_subproduto_raw = request.form.get("id_subproduto")
    qtd_lote_raw     = request.form.get("quantidade", "").strip()
 
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                if nome_comercial and preco_venda_raw:
                    preco_venda = _parse_float(preco_venda_raw)
                    if preco_venda < 0:
                        flash("Preço inválido.", "danger")
                        return redirect(url_for("estoque_painel"))
                    cur.execute(
                        "UPDATE produtos SET preco_venda = %s WHERE nome = %s",
                        (preco_venda, nome_comercial),
                    )
                    con.commit()
                    registrar_log("ALTERAR", "PRODUTOS", f"Preço '{nome_comercial}' → R$ {preco_venda:.2f}")
                    flash(f"Preço de '{nome_comercial}' atualizado!", "success")
 
                elif id_subproduto_raw and qtd_lote_raw:
                    id_sub = int(id_subproduto_raw)
                    qtd = _parse_float(qtd_lote_raw)
                    if qtd < 0:
                        flash("Quantidade inválida.", "danger")
                        return redirect(url_for("estoque_painel"))
                    cur.execute(
                        "UPDATE subprodutos SET quantidade_atual = COALESCE(quantidade_atual,0) + %s WHERE id_subproduto = %s",
                        (qtd, id_sub),
                    )
                    con.commit()
                    registrar_log("ESTOQUE", "SUBPRODUTOS", f"Lote {qtd} → Subproduto ID {id_sub}")
                    flash("Lote registrado!", "success")
                else:
                    flash("Dados insuficientes.", "warning")
    except Exception as e:
        log_erro(f"Erro ao registrar lote: {e}")
        flash(f"Erro: {e}", "danger")
 
    return redirect(url_for("estoque_painel"))
 
 
# =============================================================
# VENDAS
# =============================================================
@app.route("/vendas")
@login_required
def pagina_vendas():
    try:
        return render_template(
            "vendas.html",
            produtos=produtos.buscar_produto_por_nome("") or [],
            historico_vendas=vendas.listar_vendas_recentes() or [],
        )
    except Exception as e:
        log_erro(f"Erro na página de vendas: {e}")
        flash("Erro ao carregar vendas.", "danger")
        return redirect("/")
 
 
@app.route("/vender", methods=["POST"])
@login_required
@limiter.limit("60 per minute")
def vender():
    id_p_raw = request.form.get("id_produto", "")
    qtd_raw  = request.form.get("quantidade", "")
 
    if not id_p_raw.isdigit() or not qtd_raw.isdigit():
        flash("Dados inválidos.", "danger")
        return redirect("/vendas")
 
    id_p = int(id_p_raw)
    qtd  = int(qtd_raw)
 
    if qtd <= 0:
        flash("Quantidade deve ser maior que zero.", "warning")
        return redirect("/vendas")
 
    prods = produtos.buscar_produto_por_nome("") or []
    produto = next((p for p in prods if p[0] == id_p), None)
    if not produto:
        flash("Produto não encontrado.", "danger")
        return redirect("/vendas")
 
    valor_total = float(produto[2]) * qtd
 
    if not receitas.validar_estoque_suficiente(id_p, qtd):
        flash("Estoque insuficiente.", "danger")
        return redirect("/vendas")
 
    usuario_atual = getattr(current_user, "username", "Sistema")
    if vendas.registrar_venda(id_produto=id_p, quantidade=qtd, valor_total=valor_total, usuario=usuario_atual):
        registrar_log("VENDA", "VENDAS", f"Prod {id_p} | Qtd {qtd} | R$ {valor_total:.2f}")
        flash("Venda registrada!", "success")
    else:
        flash("Erro ao registrar venda.", "danger")
 
    return redirect("/vendas")
 
 
@app.route("/deletar-venda/<int:id_venda>")
@login_required
@acesso_requerido("vendas")
def deletar_venda(id_venda):
    if vendas.excluir_venda(id_venda):
        registrar_log("ESTORNO", "VENDAS", f"Venda {id_venda} cancelada por '{current_user.username}'")
        flash("Venda estornada e estoque devolvido!", "success")
    else:
        flash("Não foi possível estornar a venda.", "warning")
    return redirect("/vendas")
 
 
# =============================================================
# SCANNER INTELIGENTE
# =============================================================
@app.route("/estoque/escanear-inteligente", methods=["POST"])
@login_required
@limiter.limit("15 per minute")
def escanear_inteligente():
    try:
        codigo = request.form.get("codigo_barras")
        if codigo:
            with get_conn() as con:
                with con.cursor() as cur:
                    cur.execute(
                        "SELECT id_produto, nome FROM produtos WHERE codigo_barras = %s", (codigo,)
                    )
                    p = cur.fetchone()
            if p:
                return jsonify({"status": "sucesso", "acao": "adicionar", "id_produto": p[0], "nome": p[1]})
            return jsonify({"status": "novo", "acao": "cadastrar", "codigo_barras": codigo})
 
        if "foto_produto" in request.files:
            file = request.files["foto_produto"]
            if file.filename:
                imagem_bytes = file.read()
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        {"mime_type": file.content_type or "image/jpeg", "data": imagem_bytes},
                        "Identifique o nome comercial exato do produto nesta imagem. Retorne APENAS o nome, sem explicações.",
                    ],
                )
                nome_id = response.text.strip() if response.text else ""
                if not nome_id:
                    return jsonify({"status": "erro", "mensagem": "IA não identificou o produto."}), 422
 
                with get_conn() as con:
                    with con.cursor() as cur:
                        cur.execute(
                            "SELECT id_produto, nome FROM produtos WHERE nome ILIKE %s",
                            (f"%{nome_id}%",),
                        )
                        similar = cur.fetchone()
 
                if similar:
                    return jsonify({"status": "sucesso", "acao": "adicionar",
                                    "id_produto": similar[0], "nome": similar[1], "ia_detectou": nome_id})
                return jsonify({"status": "novo", "acao": "cadastrar", "nome_sugerido": nome_id})
 
        return jsonify({"status": "erro", "mensagem": "Nenhum dado recebido."}), 400
    except Exception as e:
        log_erro(f"Erro scanner inteligente: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
 
 
# =============================================================
# PREVISÃO DE ESTOQUE
# =============================================================
@app.route("/previsao-estoque")
@login_required
def previsao_estoque():
    try:
        previsoes = estoque.previsao_demanda()
        return render_template("previsao.html", previsoes=previsoes)
    except Exception as e:
        log_erro(f"Erro na previsão de estoque: {e}")
        flash(f"Erro ao processar previsão: {e}", "danger")
        return redirect(url_for("dashboard"))
 
 
# =============================================================
# EXPORTAÇÕES (CSV / EXCEL / PDF)
# =============================================================
@app.route("/exportar-previsao/csv")
@login_required
def exportar_previsao_csv():
    try:
        previsoes = estoque.previsao_demanda()
        if not previsoes:
            flash("Nenhum dado de previsão disponível.", "warning")
            return redirect("/")
 
        output = io.StringIO()
        output.write("\ufeff")
        writer = csv.writer(output, delimiter=";")
        writer.writerow([
            "Matéria-Prima", "Unidade", "Estoque Atual", "Consumo Médio Diário",
            "Consumo 7 Dias", "Consumo 15 Dias", "Dias Restantes", "Nível de Risco", "Sugestão de Compra",
        ])
        for item in previsoes:
            writer.writerow([
                item.get("materia_prima", "N/A"),
                item.get("unidade", "un"),
                str(item.get("estoque_atual", 0.0)).replace(".", ","),
                str(item.get("media_diaria", 0.0)).replace(".", ","),
                str(item.get("consumo_previsto", 0.0)).replace(".", ","),
                str(item.get("consumo_15d", 0.0)).replace(".", ","),
                str(item.get("dias_restantes", 0.0)).replace(".", ","),
                item.get("risco", "BAIXO"),
                str(item.get("sugestao_compra", 0.0)).replace(".", ","),
            ])
 
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=previsao_demanda.csv"
        response.headers["Content-type"] = "text/csv; charset=utf-8-sig"
        return response
    except Exception as e:
        log_erro(f"Erro ao exportar CSV: {e}")
        flash(f"Falha ao gerar CSV: {e}", "danger")
        return redirect("/")
 
 
@app.route("/exportar-previsao/excel")
@login_required
def exportar_previsao_excel():
    try:
        previsoes = estoque.previsao_demanda()
        if not previsoes:
            flash("Dados indisponíveis para Excel.", "info")
            return redirect("/")
 
        df = pd.DataFrame(previsoes).rename(columns={
            "materia_prima": "Matéria-Prima", "unidade": "Unidade",
            "estoque_atual": "Estoque Atual", "media_diaria": "Consumo Diário",
            "consumo_previsto": "Previsão 7 Dias", "consumo_15d": "Previsão 15 Dias",
            "dias_restantes": "Autonomia (Dias)", "risco": "Risco",
            "sugestao_compra": "Sugestão de Compra",
        })
 
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Previsão de Estoque")
            ws = writer.sheets["Previsão de Estoque"]
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = max(max_len + 3, 12)
 
        output.seek(0)
        return send_file(output, download_name="previsao_demanda.xlsx", as_attachment=True,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        log_erro(f"Erro ao exportar Excel: {e}")
        flash(f"Falha ao gerar Excel: {e}", "danger")
        return redirect("/")
 
 
@app.route("/exportar-previsao/pdf")
@login_required
def exportar_previsao_pdf():
    try:
        previsoes = estoque.previsao_demanda()
        if not previsoes:
            flash("Dados indisponíveis para PDF.", "info")
            return redirect("/")
 
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        st_titulo  = ParagraphStyle("titulo", parent=styles["Heading1"], fontSize=18,
                                    textColor=colors.HexColor("#1A237E"), spaceAfter=15)
        st_texto   = ParagraphStyle("texto", parent=styles["Normal"], fontSize=9, leading=12)
        st_header  = ParagraphStyle("header", parent=styles["Normal"], fontSize=9,
                                    leading=12, textColor=colors.white, fontName="Helvetica-Bold")
 
        elementos = [
            Paragraph("Relatório de Previsão de Demanda e Risco de Estoque", st_titulo),
            Spacer(1, 10),
        ]
 
        dados_tabela = [[
            Paragraph(h, st_header)
            for h in ["Matéria-Prima", "Estoque", "Autonomia", "Risco", "Sugestão"]
        ]]
 
        _COR_RISCO = {
            "CRÍTICO": colors.HexColor("#C62828"),
            "ALTO":    colors.HexColor("#EF6C00"),
            "MODERADO": colors.HexColor("#FBC02D"),
        }
        for item in previsoes:
            risco = item.get("risco", "BAIXO")
            cor   = _COR_RISCO.get(risco, colors.HexColor("#2E7D32"))
            st_r  = ParagraphStyle("risco", parent=st_texto, textColor=cor, fontName="Helvetica-Bold")
            dados_tabela.append([
                Paragraph(item.get("materia_prima", "N/A"), st_texto),
                Paragraph(f"{item.get('estoque_atual', 0)} {item.get('unidade', '')}", st_texto),
                Paragraph(f"{item.get('dias_restantes', 0)} dias", st_texto),
                Paragraph(risco, st_r),
                Paragraph(str(item.get("sugestao_compra", 0)), st_texto),
            ])
 
        tabela = Table(dados_tabela, colWidths=[160, 100, 90, 80, 90])
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A237E")),
            ("ALIGN",      (0, 0), (-1, -1), "LEFT"),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ]))
        elementos.append(tabela)
        doc.build(elementos)
 
        buffer.seek(0)
        return send_file(buffer, as_attachment=True,
                         download_name="previsao_demanda.pdf", mimetype="application/pdf")
    except Exception as e:
        log_erro(f"Erro ao exportar PDF: {e}")
        flash(f"Falha ao gerar PDF: {e}", "danger")
        return redirect("/")
 
 
# =============================================================
# FINANCEIRO
# =============================================================
@app.route("/financeiro")
@login_required
@acesso_requerido("financeiro")
def pagina_financeiro():
    try:
        dados = financeiro_operacional()
        return render_template("financeiro.html", **dados)
    except Exception as e:
        log_erro(f"Erro no financeiro: {e}")
        flash(f"Erro ao carregar financeiro: {e}", "danger")
        return redirect("/")
 
 
@app.route("/relatorio-financeiro")
@login_required
@acesso_requerido("financeiro")
def relatorio_financeiro():
    try:
        dados = relatorio_fiscal()
        return render_template(
            "relatorio_financeiro.html",
            regime_atual=dados["regime_atual"],
            faturamento=dados["faturamento"],
            lucro_atual=dados["lucro_atual"],
            imposto=dados["imposto_atual"],
            simulacoes=dados["simulacoes"],
        )
    except Exception as e:
        log_erro(f"Erro no relatório financeiro: {e}")
        flash(f"Erro: {e}", "danger")
        return redirect("/")
 
 
@app.route("/fluxo-caixa")
@login_required
@acesso_requerido("financeiro")
def fluxo_caixa():
    try:
        return render_template("fluxo_caixa.html")
    except Exception as e:
        flash("Fluxo de caixa em desenvolvimento.", "warning")
        return redirect("/")
 
 
@app.route("/despesas", methods=["GET", "POST"])
@login_required
@acesso_requerido("financeiro")
def despesas():
    if request.method == "POST":
        descricao = request.form.get("descricao", "").strip()
        valor     = _parse_float(request.form.get("valor", "0"))
 
        if not descricao:
            flash("Descrição obrigatória.", "warning")
            return redirect("/despesas")
        if valor <= 0:
            flash("Valor inválido.", "danger")
            return redirect("/despesas")
 
        try:
            with get_conn() as con:
                with con.cursor() as cur:
                    cur.execute(
                        "INSERT INTO despesas (descricao, valor, data_despesa) VALUES (%s,%s,CURRENT_DATE)",
                        (descricao, valor),
                    )
                con.commit()
            registrar_log("CADASTRAR", "DESPESAS", f"'{descricao}' R$ {valor:.2f}")
            flash("Despesa cadastrada!", "success")
        except Exception as e:
            log_erro(f"Erro ao salvar despesa: {e}")
            flash(f"Erro: {e}", "danger")
 
        return redirect("/despesas")
 
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT id_despesa, descricao, valor, TO_CHAR(data_despesa,'DD/MM/YYYY')
                    FROM despesas ORDER BY data_despesa DESC
                """)
                lista_despesas = cur.fetchall() or []
    except Exception as e:
        log_erro(f"Erro ao listar despesas: {e}")
        lista_despesas = []
 
    return render_template("despesa.html", despesas=lista_despesas)
 
 
# =============================================================
# AUDITORIA
# =============================================================
def _listar_logs(limite=100, usuario=None, acao=None, modulo=None,
                 data_inicio=None, data_fim=None) -> list:
    query = "SELECT usuario, acao, modulo, detalhe, data FROM logs WHERE 1=1"
    params: list = []
 
    if usuario:
        query += " AND LOWER(usuario) LIKE LOWER(%s)"
        params.append(f"%{usuario}%")
    if acao:
        query += " AND acao = %s"
        params.append(acao)
    if modulo:
        query += " AND modulo = %s"
        params.append(modulo)
    if data_inicio:
        query += " AND DATE(data) >= %s"
        params.append(data_inicio)
    if data_fim:
        query += " AND DATE(data) <= %s"
        params.append(data_fim)
 
    query += " ORDER BY data DESC LIMIT %s"
    params.append(limite)
 
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
    except Exception as e:
        log_erro(f"Erro ao consultar logs: {e}")
        return []
 
 
@app.route("/auditoria")
@login_required
@acesso_requerido("auditoria")
def auditoria():
    usuario_f  = request.args.get("usuario", "").strip()
    acao_f     = request.args.get("acao", "").strip()
    modulo_f   = request.args.get("modulo", "").strip()
    data_ini   = request.args.get("data_inicio", "").strip()
    data_fim   = request.args.get("data_fim", "").strip()
    try:
        limite = max(1, min(int(request.args.get("limite", 100)), 1000))
    except (ValueError, TypeError):
        limite = 100
 
    logs_data = _listar_logs(limite, usuario_f, acao_f, modulo_f, data_ini, data_fim)
    return render_template(
        "auditoria.html",
        logs=logs_data,
        usuario_filtro=usuario_f, acao_filtro=acao_f, modulo_filtro=modulo_f,
        data_inicio=data_ini, data_fim=data_fim, limite=limite,
    )
 
 
@app.route("/logs/exportar")
@login_required
@acesso_requerido("auditoria")
def exportar_logs():
    logs_brutos = _listar_logs(limite=1000)
    logs_fmt = []
    for log in logs_brutos:
        try:
            u, a, m, d, dt = log[:5]
            logs_fmt.append({"usuario": u, "acao": a, "modulo": m, "detalhe": d, "data": str(dt)})
        except (IndexError, TypeError):
            continue
 
    registrar_log("EXPORT_LOGS", "AUDITORIA", "Backup exportado via JSON")
    return Response(
        json.dumps(logs_fmt, indent=4, ensure_ascii=False),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=auditoria_pupilos.json"},
    )
 
 
# =============================================================
# USUÁRIOS / EQUIPE
# =============================================================
def _requer_nivel(*niveis):
    if session.get("nivel") not in niveis:
        flash("Acesso negado!", "danger")
        return True
    return False
 
 
@app.route("/equipe")
@login_required
def gerenciar_equipe():
    if _requer_nivel("admin", "socios"):
        return redirect(url_for("dashboard"))
    try:
        return render_template("equipe.html", equipe=usuarios.listar_usuarios() or [])
    except Exception as e:
        flash("Erro ao carregar equipe.", "danger")
        return redirect(url_for("dashboard"))
 
 
@app.route("/usuarios")
@login_required
def listar_usuarios_view():
    if _requer_nivel("admin", "socios"):
        return redirect(url_for("dashboard"))
    return render_template("usuarios.html", equipe=usuarios.listar_usuarios() or [])
 
 
@app.route("/usuarios/excluir/<int:id>", methods=["POST"])
@login_required
@acesso_requerido("admin")
def deletar_user(id):
    if usuarios.excluir_usuario(id):
        flash("Usuário removido!", "success")
    else:
        flash("Erro ao remover usuário.", "danger")
    return redirect("/usuarios")
 
 
@app.route("/criar-usuario", methods=["POST"])
@login_required
def criar_usuario():
    if session.get("nivel") != "admin":
        flash("Apenas administradores podem criar usuários.", "danger")
        return redirect(url_for("listar_usuarios_view"))
 
    username = request.form.get("username", "").strip().lower()
    senha    = request.form.get("senha", "").strip()
    nivel    = request.form.get("nivel", "").strip().lower()
 
    if not username or not senha or not nivel:
        flash("Todos os campos são obrigatórios.", "warning")
        return redirect(url_for("listar_usuarios_view"))
 
    if usuarios.criar_usuario(username, senha, nivel):
        registrar_log("CRIAR_USUARIO", "USUARIOS", f"{username} | Nível: {nivel}")
        flash(f"Usuário '{username}' criado!", "success")
    else:
        flash("Usuário já pode estar em uso.", "danger")
 
    return redirect(url_for("listar_usuarios_view"))
 
 
@app.route("/toggle-usuario/<int:id_usuario>")
@login_required
def toggle_usuario(id_usuario):
    if session.get("nivel") != "admin":
        flash("Permissão insuficiente.", "danger")
        return redirect(url_for("listar_usuarios_view"))
 
    usuario = usuarios.buscar_usuario_id(id_usuario)
    if not usuario:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("listar_usuarios_view"))
 
    ativo_atual = int(usuario[4] if len(usuario) > 4 else 1)
    novo_status = 0 if ativo_atual == 1 else 1
 
    if usuarios.alterar_status(id_usuario, novo_status):
        status_txt = "ativado" if novo_status == 1 else "desativado"
        registrar_log("ALTERAR_STATUS", "USUARIOS", f"ID {id_usuario} {status_txt}")
        flash(f"Conta {status_txt}!", "success")
    else:
        flash("Falha ao atualizar status.", "danger")
 
    return redirect(url_for("listar_usuarios_view"))
 
 
@app.route("/usuarios/editar/<int:id_usuario>", methods=["POST"])
@login_required
def editar_usuario(id_usuario):
    if _requer_nivel("admin", "socios"):
        return redirect(url_for("dashboard"))
 
    nivel      = request.form.get("nivel", "").strip().lower()
    nova_senha = request.form.get("nova_senha", "").strip()
 
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                if nova_senha:
                    cur.execute(
                        "UPDATE usuarios SET nivel=%s, senha=%s WHERE id_usuario=%s",
                        (nivel, generate_password_hash(nova_senha), id_usuario),
                    )
                else:
                    cur.execute(
                        "UPDATE usuarios SET nivel=%s WHERE id_usuario=%s",
                        (nivel, id_usuario),
                    )
            con.commit()
        registrar_log("EDIÇÃO", "USUARIOS", f"Perfil ID {id_usuario} atualizado")
        flash("Dados atualizados!", "success")
    except Exception as e:
        log_erro(f"Erro ao editar usuário: {e}")
        flash(f"Erro: {e}", "danger")
 
    return redirect(url_for("listar_usuarios_view"))
 
 
@app.route("/admin/config")
@login_required
@acesso_requerido("usuarios")
def area_admin():
    lista = usuarios.listar_usuarios() or []
    return render_template("admin_panel.html", total_usuarios=len(lista), usuarios=lista)
 
 
# =============================================================
# IMPORTAÇÕES / DELIVERY
# =============================================================
@app.route("/importacoes")
@login_required
@acesso_requerido("vendas")
def central_importacoes():
    return render_template("central_importacoes.html")
 
 
@app.route("/importar-ifood", methods=["POST"])
@login_required
@acesso_requerido("vendas")
@limiter.limit("5 per minute")
def importar_ifood():
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        flash("Nenhum arquivo selecionado.", "warning")
        return redirect(url_for("central_importacoes"))
 
    registrar_log("IMPORT_IFOOD", "VENDAS", f"Iniciado por '{current_user.username}': {arquivo.filename}")
 
    caminho_arquivo = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.filename)[1]) as tmp:
            arquivo.save(tmp.name)
            caminho_arquivo = tmp.name
 
        df                  = ler_arquivo(caminho_arquivo)
        dados_ia            = interpretar_relatorio_com_ia(df)
        vendas_normalizadas = normalizar_vendas(dados_ia)
 
        for v in vendas_normalizadas:
            v["id_produto"] = localizar_produto_erp(v["produto"])
 
        salvar_vendas(vendas_normalizadas)
        baixar_estoque_delivery(vendas_normalizadas)
        financeiro = gerar_financeiro(vendas_normalizadas)
 
        flash(
            f"Importação concluída! {len(vendas_normalizadas)} vendas. "
            f"Faturamento: R$ {financeiro['faturamento']:.2f}",
            "success",
        )
    except Exception as e:
        log_erro(f"Erro na importação iFood: {e}")
        flash(f"Erro crítico na importação: {e}", "danger")
    finally:
        if caminho_arquivo and os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)
 
    return redirect(url_for("central_importacoes"))
 
 
# =============================================================
# COMPRAS INTELIGENTES / OCR DE NOTAS
# =============================================================
@app.route("/compras-inteligentes")
@login_required
@acesso_requerido("estoque")
def compras_inteligentes():
    return render_template("compras_inteligentes.html")
 
 
 
@app.route("/processar-nota", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def processar_nota():
    """
    Recebe foto da nota fiscal, envia para o Gemini via OCR
    e exibe tela de confirmação com os itens extraídos.
 
    Bugs corrigidos vs versão anterior:
    - JSON parsing usa limpar_e_parsear_json() que trata markdown,
      objetos em vez de lista, e valores null/string nos campos numéricos
    - Valida tamanho do arquivo antes de enviar para a IA
    - Feedback específico por tipo de falha
    - total_itens passado para o template (necessário para confirmar_nota)
    """
    caminho_imagem = None
    try:
        foto = request.files.get("foto_nota")
        if not foto or not foto.filename:
            flash("Nenhuma imagem enviada.", "danger")
            return redirect("/compras-inteligentes")
 
        extensao = os.path.splitext(foto.filename)[1].lower()
        if extensao not in (".jpg", ".jpeg", ".png", ".webp"):
            flash("Formato inválido. Use JPG, PNG ou WEBP.", "danger")
            return redirect("/compras-inteligentes")
 
        os.makedirs("temp", exist_ok=True)
        caminho_imagem = os.path.join("temp", f"{uuid.uuid4()}{extensao}")
        if not validar_imagem_segura(foto):
            flash("Arquivo de imagem inválido.", "danger")
            return redirect("/compras-inteligentes")
        foto.save(caminho_imagem)
 
        # Valida tamanho — Gemini rejeita arquivos > 20MB
        tamanho_mb = os.path.getsize(caminho_imagem) / (1024 * 1024)
        if tamanho_mb > 18:
            flash("Imagem muito grande. Máximo 18MB.", "danger")
            return redirect("/compras-inteligentes")
 
        # Chama a IA
        resposta_raw = analisar_nota(caminho_imagem)
        if not resposta_raw:
            flash("A IA não processou a imagem. Tente uma foto mais nítida e bem iluminada.", "danger")
            return redirect("/compras-inteligentes")
 
        # Parse defensivo — trata todos os casos de JSON malformado
        itens = limpar_e_parsear_json(resposta_raw)
        if itens is None:
            log_erro(f"JSON inválido do Gemini: {resposta_raw[:300]}")
            flash("A IA retornou um formato inesperado. Tente novamente.", "danger")
            return redirect("/compras-inteligentes")
 
        if len(itens) == 0:
            flash("Nenhum item encontrado na nota. Verifique se a foto está legível.", "warning")
            return redirect("/compras-inteligentes")
 
        registrar_log("OCR_NOTA", "ESTOQUE", f"{len(itens)} itens extraídos por {current_user.username}")
        return render_template("resultado_nota.html", itens=itens, total_itens=len(itens))
 
    except Exception as e:
        log_erro(f"Erro inesperado ao processar nota: {e}")
        flash("Erro interno ao processar a nota fiscal.", "danger")
        return redirect("/compras-inteligentes")
    finally:
        if caminho_imagem and os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)
 
 
@app.route("/confirmar-nota", methods=["POST"])
@login_required
def confirmar_nota():
    """
    Recebe os itens confirmados/editados pelo usuário na tela de revisão
    e salva no banco: atualiza matéria-prima existente ou cria nova,
    e registra a entrada no estoque.
 
    Bug corrigido: cursor reaproveitado após fetchone dentro do loop
    causava 'cursor already closed' no psycopg2. Agora cada operação
    usa o mesmo cursor dentro de uma única transação.
    """
    try:
        total = int(request.form.get("total_itens", 0))
        if total == 0:
            flash("Nenhum item para confirmar.", "warning")
            return redirect("/compras-inteligentes")
 
        salvos = 0
        erros = []
 
        with get_conn() as conn:
            with conn.cursor() as cur:
                for i in range(total):
                    nome  = request.form.get(f"nome_{i}", "").strip()
                    qtd   = _parse_float(request.form.get(f"qtd_{i}", "0"))
                    preco = _parse_float(request.form.get(f"preco_{i}", "0"))
                    unidade = request.form.get(f"unidade_{i}", "UN").strip().upper() or "UN"
 
                    if not nome:
                        continue
                    if qtd <= 0:
                        erros.append(f"'{nome}': quantidade inválida ignorada")
                        continue
 
                    try:
                        # Busca matéria-prima existente
                        cur.execute(
                            "SELECT id_materia_prima FROM materia_prima WHERE LOWER(nome) = LOWER(%s)",
                            (nome,),
                        )
                        materia = cur.fetchone()
 
                        if materia:
                            id_materia = materia[0]
                            if preco > 0:
                                cur.execute(
                                    "UPDATE materia_prima SET preco_unitario=%s, unidade_medida=%s WHERE id_materia_prima=%s",
                                    (preco, unidade, id_materia),
                                )
                        else:
                            # Cria nova matéria-prima
                            cur.execute(
                                "INSERT INTO materia_prima (nome, unidade_medida, preco_unitario, estoque_minimo) "
                                "VALUES (%s, %s, %s, 0) RETURNING id_materia_prima",
                                (nome, unidade, preco),
                            )
                            id_materia = cur.fetchone()[0]
 
                        # Registra entrada no estoque
                        cur.execute(
                            "INSERT INTO movimentacao_estoque "
                            "(id_materia_prima, tipo_movimento, quantidade, observacao, usuario) "
                            "VALUES (%s, 'entrada', %s, 'Importação via OCR de nota fiscal', %s)",
                            (id_materia, qtd, current_user.username),
                        )
                        salvos += 1
 
                    except Exception as item_err:
                        erros.append(f"'{nome}': {item_err}")
                        log_erro(f"Erro ao salvar item '{nome}' da nota: {item_err}")
 
            conn.commit()
 
        registrar_log("CONFIRMAR_NOTA", "ESTOQUE",
                      f"{salvos} itens importados via OCR por {current_user.username}")
 
        if salvos > 0:
            flash(f"{salvos} item(ns) adicionado(s) ao estoque com sucesso!", "success")
        if erros:
            flash(f"Atenção: {len(erros)} item(ns) com problema: {' | '.join(erros)}", "warning")
 
    except Exception as e:
        log_erro(f"Erro geral ao confirmar nota: {e}")
        flash(f"Erro ao atualizar estoque: {e}", "danger")
 
    return redirect("/estoque")
 
# =============================================================
@app.route("/api/atualizar-precos", methods=["POST"])
@login_required
@limiter.limit("15 per minute")
def atualizar_precos():
    if current_user.nivel not in ("admin", "socio", "dono"):
        abort(403)
 
    data = request.json
    if not data or "itens" not in data:
        return jsonify({"status": "erro", "mensagem": "Dados inválidos"}), 400
 
    try:
        with get_conn() as con:
            with con.cursor() as cur:
                for item in data["itens"]:
                    cur.execute(
                        "UPDATE produtos SET preco_venda=%s WHERE id_produto=%s",
                        (item["novo_preco"], item["id"]),
                    )
            con.commit()
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        log_erro(f"Erro ao atualizar preços em lote: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500



new_cliente = os.getenv("CLIENTE", "").strip().lower()
@app.context_processor
def inject_empresa():
    config_path = f"clientes/{new_cliente}/config.json"

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        return {
            "EMPRESA": config.get("NOME_EMPRESA", "Nome Padrão")
        }

    return {
        "EMPRESA": "Nome Padrão"
    }
 


# =============================================================
# SECURITY HEADERS
# =============================================================
@app.after_request
def aplicar_headers_seguranca(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "script-src 'self' 'unsafe-inline' https:; "
        "font-src 'self' https: data:;"
    )

    return response
# =============================================================
# VALIDAÇÃO DE IMAGEM
# =============================================================

def validar_imagem_segura(arquivo):
    try:

        img = Image.open(arquivo)
        img.verify()
        arquivo.seek(0)
        return True
    except Exception:
        return False
    


 
# =============================================================
# INICIALIZAÇÃO
# =============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
