import os
import csv
import io
import json
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from flask import Response
from datetime import datetime
from functools import wraps
from modules.financeiro import (
    financeiro_operacional,
    calcular_financeiro_com_imposto,
    get_config_empresa,
    calcular_imposto,
    relatorio_fiscal
)
from flask import (
    Flask,
    render_template,
    make_response,
    request,
    redirect,
    url_for,
    flash,
    abort,
    session,
    send_file
)

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

# módulos
from modules import (
    usuarios,
    vendas,
    estoque,
    produtos,
    receitas,
    previsao
)

from modules.previsao import prever_consumo_materia_prima
from modules.permissoes import acesso_requerido
from modules.usuarios import registrar_log_db
from modules.db import conectar
import psycopg2

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

    try:

        if usuario_manual:

            usuario_log = usuario_manual

        elif current_user.is_authenticated:

            # SALVA O USERNAME
            usuario_log = current_user.username

        else:

            usuario_log = "anonimo"

        usuarios.registrar_log_db(
            usuario_log,
            acao,
            modulo,
            detalhe
        )

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

        # ============================================
        # RESUMOS
        # ============================================

        resumo_diario = vendas.obter_resumo_periodo(1)

        resumo_semanal = vendas.obter_resumo_periodo(7)

        resumo_mensal = vendas.obter_resumo_periodo(30)

        # ============================================
        # ESTOQUE
        # ============================================

        capacidade = produtos.calcular_capacidade_geral()

        insumos = estoque.listar_materia_prima()

        criticos = [
            i for i in insumos
            if float(i[4]) <= float(i[3])
        ]

        # ============================================
        # RENDER
        # ============================================

        return render_template(
            "dashboard.html",

            diario=resumo_diario,

            semana=resumo_semanal,

            mes=resumo_mensal,

            capacidade=capacidade,

            criticos=criticos
        )

    except Exception as e:

        print(f"Erro no Dashboard: {e}")

        return render_template(
            "dashboard.html",

            diario={
                "faturamento": 0,
                "total_vendas": 0,
                "lucro": 0
            },

            semana={
                "faturamento": 0,
                "total_vendas": 0,
                "lucro": 0
            },

            mes={
                "faturamento": 0,
                "total_vendas": 0,
                "lucro": 0
            },

            capacidade=[],

            criticos=[]
        )

# =========================
# ESTOQUE
# =========================


@app.route("/compras")
@login_required
def pagina_compras():
    return render_template("compras.html", materias=estoque.listar_materia_prima())


@app.route("/registrar-producao", methods=["POST"])
@login_required
@acesso_requerido("estoque")
def registrar_producao():
    try:
        tipo_item = request.form.get("tipo_item") # 'subproduto' ou 'produto'
        id_item = int(request.form.get("id_item"))
        qtd = float(request.form.get("quantidade").replace(",", "."))
        
        # Aqui dispara a sua regra de negócio interna para dar entrada no item produzido
        # e dar a baixa automática nos ingredientes utilizados da receita.
        if tipo_item == "subproduto":
            estoque.entrada_subproduto(id_item, qtd) # Função que implementaremos no estoque
            registrar_log("PRODUCAO", "SUBPRODUTO", f"ID {id_item} | Qtd {qtd}")
        elif tipo_item == "produto":
            estoque.entrada_produto(id_item, qtd)
            registrar_log("PRODUCAO", "PRODUTO", f"ID {id_item} | Qtd {qtd}")
            
        flash("Produção registrada com sucesso e estoque atualizado!", "success")
    except Exception as e:
        flash(f"Erro ao registrar produção: {e}", "danger")
        
    return redirect("/estoque")

# =====================================================================
# --- ROTA: PAINEL GLOBAL DE ESTOQUE (COM HISTÓRICO UNIFICADO) ---
# =====================================================================
@app.route("/estoque")
@login_required
@acesso_requerido("estoque")
def estoque_page():
    try:
        # Busca os dados unificados do banco de dados exatamente como o estoque.html precisa
        lista_materias = estoque.listar_materias_primas() if hasattr(estoque, 'listar_materias_primas') else []
        lista_subprodutos = estoque.listar_subprodutos() if hasattr(estoque, 'listar_subprodutos') else []
        lista_produtos = estoque.listar_produtos_finais() if hasattr(estoque, 'listar_produtos_finais') else (produtos.listar_todos() if 'produtos' in globals() else [])
        
        return render_template(
            "estoque.html", 
            materias=lista_materias, 
            subprodutos=lista_subprodutos, 
            produtos=lista_produtos
        )
    except Exception as e:
        flash(f"Erro ao carregar o painel de estoque: {e}", "danger")
        return redirect(url_for('index'))  # Redireciona para a home caso dê algum erro interno


@app.route("/estoque/balanco-diario")
@login_required
@acesso_requerido("estoque")
def balanco_diario_page():  # NOME EXCLUSIVO: Sem conflito de endpoint!
    try:
        # 1. Captura a data enviada pelo filtro do HTML (?data=AAAA-MM-DD). Se não houver, usa a data de hoje.
        data_param = request.args.get('data')
        if data_param:
            hoje_str = data_param
            # Formata para exibição amigável no topo do card (Ex: 2026-05-19 vira 19/05/2026)
            try:
                ano, mes, dia = hoje_str.split('-')
                data_exibicao = f"{dia}/{mes}/{ano}"
            except ValueError:
                data_exibicao = hoje_str
        else:
            hoje_str = datetime.now().strftime("%Y-%m-%d")
            data_exibicao = datetime.now().strftime("%d/%m/%Y")

        # 2. Busca a lista de produtos cadastrados para pegar o Saldo Atual
        lista_produtos = estoque.listar_produtos_finais() if hasattr(estoque, 'listar_produtos_finais') else (produtos.listar_todos() if 'produtos' in globals() else [])
        
        # 3. Busca o histórico de vendas completo
        historico_vendas = estoque.listar_vendas() if hasattr(estoque, 'listar_vendas') else []
        
        balanco = []
        
        for p in lista_produtos:
            id_produto = p[0]
            nome_produto = p[1]
            
            # Tratamento de índice seguro para capturar o saldo atual do produto
            dado_sobrou = p[4] if len(p) > 4 else (p[3] if len(p) > 3 else 0) 
            
            # BLINDAGEM DE TIPAGEM: Garante que a sobra sempre seja um número inteiro
            try:
                sobrou = int(dado_sobrou) if dado_sobrou is not None else 0
            except (ValueError, TypeError):
                sobrou = 0
            
            # Calcular quanto vendeu desse produto especificamente na data escolhida (hoje_str)
            vendido_hoje = 0
            for v in historico_vendas:
                if hasattr(v, 'id_produto') or isinstance(v, dict):
                    v_id = v.get('id_produto') if isinstance(v, dict) else v.id_produto
                    v_data = v.get('data') if isinstance(v, dict) else v.data
                    v_qtd = v.get('quantidade') if isinstance(v, dict) else v.quantidade
                else:
                    v_id = v[2]    
                    v_data = v[1]  
                    v_qtd = v[3]   
                
                v_data_str = v_data if isinstance(v, str) else v_data.strftime("%Y-%m-%d") if hasattr(v_data, 'strftime') else str(v_data)
                
                # Procura a correspondência exata do ID do produto e se a data de busca está contida no registro
                if str(v_id) == str(id_produto) and hoje_str in v_data_str:
                    # BLINDAGEM DE VENDAS
                    try:
                        vendido_hoje += int(v_qtd)
                    except (ValueError, TypeError):
                        pass
            
            # Matemática de Engenharia Reversa: Fabricado = Sobra + Vendas
            feito_hoje = sobrou + vendido_hoje
            
            balanco.append({
                "id": id_produto,
                "nome": nome_produto,
                "feito": feito_hoje,
                "vendido": vendido_hoje,
                "sobrou": sobrou
            })
            
        # Retorna o template passando as variáveis dinâmicas de data de busca atual
        return render_template(
            "balanco_diario.html", 
            data_hoje=data_exibicao, 
            data_busca_atual=hoje_str, 
            datetime_hoje=datetime.now().strftime("%Y-%m-%d"),
            balanco=balanco
        )
        
    except Exception as e:
        flash(f"Erro ao gerar balanço diário: {e}", "danger")
        return redirect(url_for('estoque_page'))

# =====================================================================
# --- ROTA: ATUALIZAR PRODUTO (CORRIGIDA E SEGURA) ---
# =====================================================================
@app.route("/editar-produto/<int:id_produto>", methods=["POST"])
@login_required
def atualizar_produto(id_produto):  # <-- AGORA RECEBENDO O ID CORRETAMENTE

    try:
        nome = request.form.get("nome", "").strip()
        preco = request.form.get("preco", 0)

        sucesso = usuarios.update_produto(
            id_produto,
            nome,
            preco
        )

        if sucesso:
            flash(
                "Produto updated com sucesso!",
                "success"
            )
        else:
            flash(
                "Erro ao atualizar produto.",
                "danger"
            )

    except Exception as e:
        print(f"Erro rota atualizar produto: {e}")
        flash(
            f"Erro: {e}",
            "danger"
        )

    # Retorna para a página unificada de estoque do sistema
    return redirect(url_for("estoque_page"))


@app.route("/editar-materia-prima/<int:id_mp>", methods=["POST"])
@login_required
def processar_edicao_mp(id_mp):

    try:

        nome = request.form.get("nome", "").strip()

        preco = request.form.get("preco_custo", 0)

        unidade = request.form.get("unidade", "").strip()

        quantidade = request.form.get("quantidade", 0)

        sucesso = usuarios.atualizar_materia_prima(
            id_mp,
            nome,
            preco,
            unidade,
            quantidade
        )

        if sucesso:

            flash(
                "Matéria-prima atualizada com sucesso!",
                "success"
            )

        else:

            flash(
                "Erro ao tentar atualizar.",
                "danger"
            )

    except Exception as e:

        print(f"Erro rota editar MP: {e}")

        flash(
            f"Erro: {e}",
            "danger"
        )

    return redirect(url_for('estoque_page'))




# =========================
# CADASTRO PRODUTOS/MATERIA-PRIMA
# =========================
# --- ROTA PRINCIPAL DA CENTRAL DE CADASTROS ---
@app.route("/cadastro")
@login_required
def render_cadastro():
    try:
        # Carrega dados para preencher os selects da Ficha Técnica
        lista_produtos = produtos.listar_todos() 
        lista_materias = estoque.listar_materia_prima()
        
        # Correção da linha do hasattr e alinhamento do Python
        if hasattr(estoque, 'listar_subprodutos'):
            lista_subprodutos = estoque.listar_subprodutos()
        else:
            lista_subprodutos = []
        
        # IMPORTANTE: Adicionado 'subprodutos=lista_subprodutos' para enviar ao HTML
        return render_template("cadastro.html", 
                               produtos=lista_produtos, 
                               materias=lista_materias,
                               subprodutos=lista_subprodutos)
    except Exception as e:
        print(f"Erro ao carregar cadastro: {e}")
        flash(f"Erro ao carregar dados: {e}", "danger")
        return redirect("/")

# --- AÇÃO: CADASTRAR MATÉRIA-PRIMA (INSUMOS) ---
@app.route("/cadastrar-mp", methods=["POST"])
@login_required
def cadastrar_mp():
    try:
        nome = request.form.get("nome")
        unidade = request.form.get("unidade")
        preco = float(request.form.get("preco").replace(",", "."))
        estoque_at = float(request.form.get("estoque_atual").replace(",", "."))
        estoque_min = float(request.form.get("estoque_minimo").replace(",", "."))
        
        # Usando a função do estoque.py que já mapeamos para o banco
        if estoque.cadastrar_materia(nome, unidade, preco, estoque_at, estoque_min):
            flash(f"Insumo '{nome}' salvo!", "success")
        else:
            flash("Erro ao salvar no banco.", "danger")
    except Exception as e:
        flash(f"Erro: {e}", "danger")
    return redirect(url_for('render_cadastro'))

# --- AÇÃO: CADASTRAR PRODUTO FINAL ---
@app.route("/cadastrar-produto", methods=["POST"])
@login_required
def cadastrar_produto_final():
    try:
        nome = request.form.get("nome")
        preco = float(request.form.get("preco").replace(",", "."))
        categoria = request.form.get("categoria")
        
        if produtos.cadastrar_produto(nome, preco, categoria):
            registrar_log("CADASTRO", "PRODUTO", f"Novo produto: {nome}")
            flash(f"Produto '{nome}' cadastrado com sucesso!", "success")
        else:
            flash("Erro ao cadastrar produto final.", "danger")
    except Exception as e:
        flash(f"Erro nos dados: {e}", "danger")
        
    return redirect(url_for('render_cadastro'))

# --- AÇÃO: VINCULAR RECEITA (ENGENHARIA) ---
@app.route("/vincular-receita", methods=["POST"])
@login_required
def vincular_receita():
    try:
        # Pegando os IDs que vêm do formulário HTML
        id_p = request.form.get("id_produto")
        id_m = request.form.get("id_materia_prima")
        qtd = float(request.form.get("quantidade").replace(",", "."))
        
        if produtos.vincular_insumo(id_p, id_m, qtd):
            flash("Ingrediente vinculado!", "success")
        else:
            flash("Erro ao vincular.", "danger")
    except Exception as e:
        flash(f"Erro: {e}", "danger")
    return redirect(url_for('render_cadastro'))


# --- ROTA: EXCLUIR PRODUTO ---
@app.route("/excluir-produto/<int:id_produto>")
@login_required
def deletar_produto(id_produto):

    if session.get("nivel") not in ["admin", "socios"]:

        flash(
            "Acesso negado! Apenas socios podem excluir produtos.",
            "danger"
        )

        return redirect(url_for('estoque_page'))

    try:

        sucesso = usuarios.excluir_produto(id_produto)

        if sucesso:

            registrar_log(
                session.get('user'),
                "EXCLUIR",
                "ESTOQUE",
                f"Removeu produto ID {id_produto}"
            )

            flash(
                "Produto removido com sucesso!",
                "success"
            )

        else:

            flash(
                "Erro ao excluir produto.",
                "danger"
            )

    except Exception as e:

        flash(
            f"Erro ao excluir: {e}",
            "danger"
        )

    return redirect(url_for('estoque_page'))

# --- ROTA: EXCLUIR MATÉRIA-PRIMA ---
@app.route("/excluir-mp/<int:id_mp>")
@login_required
def deletar_mp(id_mp):

    if session.get("nivel") not in ["admin", "socios"]:

        flash(
            "Permissão insuficiente.",
            "danger"
        )

        return redirect(url_for('estoque_page'))

    try:

        sucesso = usuarios.excluir_materia_prima(id_mp)

        if sucesso:

            registrar_log(
                session.get('user'),
                "EXCLUIR",
                "MATERIA_PRIMA",
                f"Removeu insumo ID {id_mp}"
            )

            flash(
                "Matéria-prima removida!",
                "success"
            )

        else:

            flash(
                "Erro ao excluir matéria-prima.",
                "danger"
            )

    except Exception as e:

        flash(
            f"Erro ao excluir: {e}",
            "danger"
        )

    return redirect(url_for('estoque_page'))

# --- ROTA: EXCLUIR VENDA ---
@app.route("/excluir-venda/<int:id_venda>")
@login_required
def deletar_venda(id_venda):

    if session.get("nivel") not in ["admin", "socios"]:

        flash(
            "Acesso negado! Apenas Socios podem excluir vendas.",
            "danger"
        )

        return redirect(url_for('vendas_page'))

    try:

        sucesso = usuarios.excluir_venda(id_venda)

        if sucesso:

            registrar_log(
                session.get('user'),
                "EXCLUIR",
                "VENDAS",
                f"Removeu venda ID {id_venda}"
            )

            flash(
                "Venda excluída com sucesso!",
                "success"
            )

        else:

            flash(
                "Erro ao excluir venda.",
                "danger"
            )

    except Exception as e:

        flash(
            f"Erro ao excluir venda: {e}",
            "danger"
        )

    return redirect(url_for('vendas_page'))


@app.route("/estoque/fechamento")
@login_required
@acesso_requerido("estoque")
def fechamento_diario():
    # Código sênior que vai buscar:
    # 1. Quantidade fabricada hoje de cada produto
    # 2. Quantidade vendida hoje de cada produto
    # 3. Cálculo matemático (Fabricado - Vendido) para mostrar a sobra
    dados_fechamento = estoque.obter_balanco_diario() 
    return render_template("fechamento.html", balanco=dados_fechamento)

# =========================================================
# NEW AÇÃO: CADASTRAR SUBPRODUTO / MATÉRIA-BASE (Ex: Brownie)
# =========================================================
@app.route("/cadastrar-subproduto", methods=["POST"])
@login_required
def cadastrar_subproduto():
    try:
        nome = request.form.get("nome").strip()
        unidade = request.form.get("unidade").strip()
        estoque_min = float(request.form.get("estoque_minimo", "0").replace(",", "."))
        
        # O estoque inicial do subproduto começa zerado (ele entra quando for produzido!)
        if estoque.cadastrar_subproduto_banco(nome, unidade, estoque_min):
            registrar_log(session.get('user', 'admin'), "CADASTRO", "SUBPRODUTO", f"Novo subproduto: {nome}")
            flash(f"Subproduto '{nome}' cadastrado com sucesso!", "success")
        else:
            flash("Erro ao cadastrar subproduto no banco.", "danger")
    except Exception as e:
        flash(f"Erro nos dados do subproduto: {e}", "danger")
        
    return redirect(url_for('render_cadastro'))


# =========================================================
# NEW AÇÃO: VINCULAR RECEITA DO SUBPRODUTO (Ficha Técnica do Brownie)
# =========================================================
@app.route("/vincular-receita-subproduto", methods=["POST"])
@login_required
def vincular_receita_subproduto():
    try:
        id_sub = request.form.get("id_subproduto")
        id_m = request.form.get("id_materia_prima")
        qtd = float(request.form.get("quantidade").replace(",", "."))
        
        if estoque.vincular_insumo_subproduto(id_sub, id_m, qtd):
            flash("Ingrediente vinculado ao subproduto com sucesso!", "success")
        else:
            flash("Erro ao vincular ingrediente ao subproduto.", "danger")
    except Exception as e:
        flash(f"Erro ao vincular: {e}", "danger")
        
    return redirect(url_for('render_cadastro'))


# =========================================================
# NEW AÇÃO: VINCULAR SUBPRODUTO AO PRODUTO FINAL (Ex: Brownie no Copo da Felicidade)
# =========================================================
@app.route("/vincular-subproduto-produto", methods=["POST"])
@login_required
def vincular_subproduto_produto():
    try:
        id_p = request.form.get("id_produto")
        id_sub = request.form.get("id_subproduto")
        qtd = float(request.form.get("quantidade").replace(",", "."))
        
        if produtos.vincular_subproduto_ao_produto(id_p, id_sub, qtd):
            flash("Subproduto/Matéria-base vinculada ao produto com sucesso!", "success")
        else:
            flash("Erro ao vincular subproduto ao produto.", "danger")
    except Exception as e:
        flash(f"Erro: {e}", "danger")
        
    return redirect(url_for('render_cadastro'))

# =========================================================
# NEW ROTA: EXCLUIR SUBPRODUTO (Segurança máxima)
# =========================================================
@app.route("/excluir-subproduto/<int:id_subproduto>")
@login_required
def deletar_subproduto(id_subproduto):
    if session.get("nivel") not in ["admin", "socios"]:
        flash("Acesso negado! Apenas sócios podem excluir subprodutos.", "danger")
        return redirect(url_for('estoque_page'))

    try:
        sucesso = estoque.excluir_subproduto_banco(id_subproduto)
        if sucesso:
            registrar_log(
                session.get('user'),
                "EXCLUIR",
                "SUBPRODUTO",
                f"Removeu subproduto ID {id_subproduto}"
            )
            flash("Subproduto removido com sucesso!", "success")
        else:
            flash("Erro ao excluir subproduto.", "danger")
    except Exception as e:
        flash(f"Erro ao excluir subproduto: {e}", "danger")

    return redirect(url_for('estoque_page'))

# --- ROTA: PRECIFICAÇÃO ---
from psycopg2.extras import RealDictCursor

@app.route("/precificacao")
@login_required
def precificacao():
    con = None
    try:
        con = conectar()
        cursor = con.cursor(cursor_factory=RealDictCursor)
        
        # SQL ajustado para os nomes exatos das suas tabelas
        query = """
            SELECT 
                p.id_produto, 
                p.nome, 
                p.preco_venda,
                COALESCE(SUM(r.quantidade_utilizada * mp.preco_unitario), 0) as custo_producao
            FROM produtos p
            LEFT JOIN receitas r ON p.id_produto = r.id_produto
            LEFT JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
            WHERE p.ativo = 1
            GROUP BY p.id_produto, p.nome, p.preco_venda
            ORDER BY p.nome ASC
        """
        cursor.execute(query)
        produtos_db = cursor.fetchall()
        
        tabela_formatada = []
        for p in produtos_db:
            custo = float(p['custo_producao'])
            venda = float(p['preco_venda'])
            
            equilibrio = custo * 1.10
            sugerido = custo / 0.7 if custo > 0 else 0
            
            tabela_formatada.append({
                "id": p['id_produto'],
                "nome": p['nome'],
                "atual": venda,
                "equilibrio": equilibrio,
                "sugerido": sugerido,
                "alerta": venda < equilibrio if custo > 0 else False
            })

        return render_template("precificacao.html", tabela=tabela_formatada)
    finally:
        if con: con.close()
# =========================
# VENDAS
# =========================
@app.route("/vendas")
@login_required
@acesso_requerido("vendas")
def vendas_page():

    lista_produtos = produtos.buscar_produto_por_nome("")

    historico_vendas = vendas.listar_vendas_recentes()

    return render_template(
        "vendas.html",
        produtos=lista_produtos,
        historico_vendas=historico_vendas
    )

@app.route("/vender", methods=["POST"])
@login_required
def vender():

    try:

        id_p = int(request.form["id_produto"])
        qtd = int(request.form["quantidade"])

        # =====================================================
        # BUSCA PRODUTO
        # =====================================================

        prods = produtos.buscar_produto_por_nome("")

        produto = next(
            (p for p in prods if p[0] == id_p),
            None
        )

        if not produto:

            flash("Produto não encontrado", "danger")

            return redirect("/vendas")

        # =====================================================
        # VALOR TOTAL
        # =====================================================

        valor_total = float(produto[2]) * qtd

        # =====================================================
        # VALIDA ESTOQUE
        # =====================================================

        estoque_ok = vendas.validar_estoque_suficiente(
            id_p,
            qtd
        )

        if not estoque_ok:

            flash(
                "Estoque insuficiente para produzir essa venda.",
                "danger"
            )

            return redirect("/vendas")

        # =====================================================
        # REGISTRA VENDA
        # =====================================================

        sucesso = vendas.registrar_venda(
            id_produto=id_p,
            quantidade=qtd,
            valor_total=valor_total,
            usuario=current_user.username
        )

        # =====================================================
        # RESULTADO
        # =====================================================

        if sucesso:

            registrar_log(
                "VENDA",
                "VENDAS",
                f"Produto {id_p} | Qtd {qtd}"
            )

            flash(
                "Venda registrada com sucesso!",
                "success"
            )

        else:

            flash(
                "Erro ao registrar venda.",
                "danger"
            )

    except Exception as e:

        print(f"Erro rota vender: {e}")

        flash(
            f"Erro ao vender: {e}",
            "danger"
        )

    return redirect("/vendas")

# =========================
#  AUDITORIA
# =========================
# =========================================================
# ROTA: TELA DE AUDITORIA (Visualizar Logs no Navegador)
# =========================================================
# =========================
# AUDITORIA
# =========================
@app.route("/auditoria")
@login_required
@acesso_requerido("auditoria")
def auditoria():

    try:

        # =========================================
        # FILTROS (QUERY PARAMS)
        # =========================================

        usuario_filtro = request.args.get("usuario", "").strip()

        acao_filtro = request.args.get("acao", "").strip()

        modulo_filtro = request.args.get("modulo", "").strip()

        data_inicio = request.args.get("data_inicio", "").strip()

        data_fim = request.args.get("data_fim", "").strip()

        limite = request.args.get("limite", 100)

        # =========================================
        # HARDENING LIMITE
        # =========================================

        try:

            limite = int(limite)

            if limite <= 0:
                limite = 100

            if limite > 1000:
                limite = 1000

        except:

            limite = 100

        # =========================================
        # BUSCA LOGS
        # =========================================

        logs_data = usuarios.listar_logs_auditoria_filtrado(
            limite=limite,
            usuario=usuario_filtro,
            acao=acao_filtro,
            modulo=modulo_filtro,
            data_inicio=data_inicio,
            data_fim=data_fim
        )

        # =========================================
        # RENDER
        # =========================================

        return render_template(
            "auditoria.html",
            logs=logs_data,

            # Mantém filtros preenchidos
            usuario_filtro=usuario_filtro,
            acao_filtro=acao_filtro,
            modulo_filtro=modulo_filtro,
            data_inicio=data_inicio,
            data_fim=data_fim,
            limite=limite
        )

    except Exception as e:

        print(f"Erro ao carregar logs: {e}")

        flash(
            f"Erro ao carregar auditoria: {e}",
            "danger"
        )

        return redirect(url_for('dashboard'))
    


# =========================================================
# LISTAR LOGS AUDITORIA FILTRADO
# =========================================================
def listar_logs_auditoria_filtrado(
    limite=100,
    usuario=None,
    acao=None,
    modulo=None,
    data_inicio=None,
    data_fim=None
):

    conn = None

    try:

        conn = conectar()

        cursor = conn.cursor()

        # =========================================
        # QUERY BASE
        # =========================================

        query = """
            SELECT
                usuario,
                acao,
                modulo,
                descricao,
                data_log
            FROM logs
            WHERE 1=1
        """

        params = []

        # =========================================
        # FILTRO USUÁRIO
        # =========================================

        if usuario:

            query += """
                AND LOWER(usuario) LIKE LOWER(%s)
            """

            params.append(f"%{usuario}%")

        # =========================================
        # FILTRO AÇÃO
        # =========================================

        if acao:

            query += """
                AND acao = %s
            """

            params.append(acao)

        # =========================================
        # FILTRO MÓDULO
        # =========================================

        if modulo:

            query += """
                AND modulo = %s
            """

            params.append(modulo)

        # =========================================
        # FILTRO DATA INÍCIO
        # =========================================

        if data_inicio:

            query += """
                AND DATE(data_log) >= %s
            """

            params.append(data_inicio)

        # =========================================
        # FILTRO DATA FIM
        # =========================================

        if data_fim:

            query += """
                AND DATE(data_log) <= %s
            """

            params.append(data_fim)

        # =========================================
        # ORDER + LIMIT
        # =========================================

        query += """
            ORDER BY data_log DESC
            LIMIT %s
        """

        params.append(limite)

        # =========================================
        # EXECUTA
        # =========================================

        cursor.execute(query, params)

        logs = cursor.fetchall()

        return logs

    except Exception as e:

        print(f"Erro listar logs filtrados: {e}")

        return []

    finally:

        if conn:
            conn.close()

# =========================================================
# ROTA: EXPORTAR LOGS (Apenas gera o download do arquivo)
# =========================================================
@app.route("/logs/exportar")
@login_required
@acesso_requerido("auditoria")
def exportar_logs():

    try:

        logs_brutos = usuarios.listar_logs_auditoria(1000)

        logs_formatados = []

        for log in logs_brutos:

            logs_formatados.append({

                "usuario": log["usuario"],
                "acao": log["acao"],
                "modulo": log["modulo"],
                "detalhe": log["detalhe"],
                "data": str(log["data"])

            })

        json_output = json.dumps(
            logs_formatados,
            indent=4,
            ensure_ascii=False
        )

        usuarios.registrar_log_db(

            usuario=current_user.username,
            acao="EXPORT_LOGS",
            modulo="AUDITORIA",
            detalhe="Backup exportado"

        )

        return Response(

            json_output,
            mimetype="application/json",
            headers={
                "Content-Disposition":
                "attachment; filename=auditoria_pupilos.json"
            }

        )

    except Exception as e:

        print(f"Erro exportar logs: {e}")

        flash(
            f"Erro ao exportar logs: {e}",
            "danger"
        )

        return redirect(url_for("auditoria"))

# =========================================================
# GERENCIAR EQUIPE
# =========================================================
@app.route("/equipe")
@login_required
def gerenciar_equipe():

    if session.get("nivel") not in ["admin", "socios"]:

        flash(
            "Acesso negado!",
            "danger"
        )

        return redirect(url_for("dashboard"))

    try:

        lista_usuarios = usuarios.listar_usuarios()

        return render_template(
            "equipe.html",
            equipe=lista_usuarios
        )

    except Exception as e:

        print(f"Erro equipe: {e}")

        flash(
            f"Erro ao carregar equipe: {e}",
            "danger"
        )

        return redirect(url_for("dashboard"))



# =========================================================
# LISTAR USUÁRIOS
# =========================================================
@app.route("/usuarios")
@login_required
def listar_usuarios():

    if session.get("nivel") not in ["admin", "socios"]:

        flash(
            "Acesso negado!",
            "danger"
        )

        return redirect(url_for("dashboard"))

    try:

        lista = usuarios.listar_usuarios()

        return render_template(
            "usuarios.html",
            equipe=lista
        )

    except Exception as e:

        print(f"Erro usuários: {e}")

        flash(
            f"Erro ao carregar usuários: {e}",
            "danger"
        )

        return redirect(url_for("dashboard"))

# =========================================================
# CRIAR USUÁRIO
# =========================================================
@app.route("/criar-usuario", methods=["POST"])
@login_required
def criar_usuario():

    if session.get("nivel") != "admin":

        flash(
            "Somente administradores podem criar usuários.",
            "danger"
        )

        return redirect(url_for("listar_usuarios"))

    try:

        username = request.form.get("username").strip().lower()

        senha = request.form.get("senha").strip()

        nivel = request.form.get("nivel").strip().lower()

        sucesso = usuarios.criar_usuario(
            username,
            senha,
            nivel
        )

        if sucesso:

            registrar_log(
                "CRIAR_USUARIO",
                "USUARIOS",
                f"Usuário criado: {username}"
            )

            flash(
                "Usuário criado com sucesso!",
                "success"
            )

        else:

            flash(
                "Erro ao criar usuário.",
                "danger"
            )

    except Exception as e:

        print(f"Erro criar usuário: {e}")

        flash(
            f"Erro: {e}",
            "danger"
        )

    return redirect(url_for("listar_usuarios"))

# =========================================================
# ATIVAR / DESATIVAR USUÁRIO
# =========================================================
@app.route("/toggle-usuario/<int:id_usuario>")
@login_required
def toggle_usuario(id_usuario):

    if session.get("nivel") != "admin":

        flash(
            "Permissão insuficiente.",
            "danger"
        )

        return redirect(url_for("listar_usuarios"))

    try:

        usuario = usuarios.buscar_usuario_id(id_usuario)

        if not usuario:

            flash(
                "Usuário não encontrado.",
                "warning"
            )

            return redirect(url_for("listar_usuarios"))

        ativo_atual = usuario[4]

        novo_status = 0 if ativo_atual == 1 else 1

        usuarios.alterar_status(
            id_usuario,
            novo_status
        )

        status_txt = (
            "ativado"
            if novo_status == 1
            else "desativado"
        )

        registrar_log(
            "ALTERAR_STATUS",
            "USUARIOS",
            f"Usuário {usuario[1]} foi {status_txt}"
        )

        flash(
            f"Usuário {status_txt} com sucesso!",
            "success"
        )

    except Exception as e:

        print(f"Erro toggle usuário: {e}")

        flash(
            f"Erro: {e}",
            "danger"
        )

    return redirect(url_for("listar_usuarios"))


@app.route("/usuarios/editar/<int:id_usuario>", methods=["POST"])
@login_required
def editar_usuario(id_usuario):
    # Proteção: Garante que só admin (ou sócios, dependendo da sua regra) pode editar
    if session.get("nivel") not in ["admin", "socios"]:
        flash("Acesso negado!", "danger")
        return redirect(url_for("dashboard"))

    nivel = request.form.get("nivel")
    nova_senha = request.form.get("nova_senha")
    
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        
        if nova_senha and len(nova_senha.strip()) > 0:
            # Atualiza nível e senha (gerando o hash correto)
            senha_hash = generate_password_hash(nova_senha.strip())
            cur.execute("""
                UPDATE usuarios 
                SET nivel = %s, senha = %s 
                WHERE id_usuario = %s
            """, (nivel, senha_hash, id_usuario))
        else:
            # Atualiza apenas nível
            cur.execute("""
                UPDATE usuarios 
                SET nivel = %s 
                WHERE id_usuario = %s
            """, (nivel, id_usuario))
            
        con.commit()
        flash("Dados atualizados com sucesso!", "success")
        
        # Corrigido para usar a sua função padrão de logs do app.py
        registrar_log("EDIÇÃO", "USUARIOS", f"Alterou dados do ID {id_usuario}")
        
    except Exception as e:
        if con: con.rollback()
        print(f"Erro ao editar usuário: {e}") # Ajuda a ver o erro no terminal
        flash(f"Erro ao atualizar: {e}", "danger")
    finally:
        if con: con.close()
        
    # CORRIGIDO: Redireciona para a sua rota real que lista a equipe/usuários
    return redirect(url_for('listar_usuarios'))




# =========================================================
# PAINEL DE ADMINISTRAÇÃO (GESTÃO DE USUÁRIOS)
# =========================================================
# 1. A ROTA CERTA DO PAINEL (Onde mostra os usuários)
@app.route("/admin/config")
@login_required
@acesso_requerido("usuarios")
def area_admin():
    try:
        # Busca usuários para listar no painel
        lista_usuarios = usuarios.listar_usuarios() 
        total = len(lista_usuarios)
        
        # Renderiza a tela de gestão de usuários
        return render_template(
            "admin_panel.html",
            total_usuarios=total,
            usuarios=lista_usuarios
        )
    except Exception as e:
        flash(f"Erro ao acessar painel: {e}", "danger")
        return redirect(url_for("dashboard"))
# =========================================================
# CENTRAL DE CADASTRO
# =========================================================
@app.route("/cadastro-central")
@login_required
def cadastro_central():

    return redirect(
        url_for("render_cadastro")
    )

# =========================================================
# CENTRAL DE IMPORTAÇÕES (AUDITADO)
# =========================================================
@app.route("/importacoes")
@login_required
@acesso_requerido("vendas") # Protege a rota para níveis autorizados
def central_importacoes():
    return render_template("central_importacoes.html")

@app.route("/importar-ifood", methods=["POST"])
@login_required
@acesso_requerido("vendas")
def importar_ifood():
    try:
        arquivo = request.files.get("arquivo")
        
        if not arquivo or arquivo.filename == '':
            flash("Nenhum arquivo selecionado!", "warning")
            return redirect(url_for("central_importacoes"))

        # Registro de Log no Banco de Dados
        usuarios.registrar_log_db(
            usuario=current_user.id,
            acao="IMPORT_IFOOD",
            modulo="VENDAS",
            detalhe=f"Importação iniciada: {arquivo.filename}"
        )

        # Aqui entraria a lógica de leitura do Pandas (pd.read_excel/csv)
        # Por enquanto, mantemos o fluxo de redirecionamento
        
        flash(f"Arquivo '{arquivo.filename}' recebido com sucesso! O processamento foi registrado.", "success")
        
    except Exception as e:
        print(f"Erro na importação: {e}")
        flash(f"Erro crítico na importação: {e}", "danger")
        
    return redirect(url_for("central_importacoes"))


# ==========================================
# ROTAS DE SUPORTE: FICHA TÉCNICA E AJUSTES DO ESTOQUE
# ==========================================

@app.route("/ficha-tecnica/<int:id_produto>")
@login_required
def ficha_tecnica(id_produto):
    con = None
    try:
        con = conectar()
        cursor = con.cursor()
        
        # 1. Busca os dados básicos do produto principal
        cursor.execute("SELECT id, nome, preco_venda FROM produtos WHERE id = %s", (id_produto,))
        produto = cursor.fetchone()
        
        if not produto:
            flash("Produto não encontrado!", "danger")
            return redirect("/estoque")

        # 2. Query Avançada Avançada (Substituído IFNULL por COALESCE para compatibilidade universal)
        query_itens = """
            SELECT 
                r.id as id_vinculo,
                'materia_prima' as tipo,
                mp.id_materia_prima as id_item,
                mp.nome as item, 
                r.quantidade_utilizada as qtd, 
                mp.unidade_medida as unidade,
                (r.quantidade_utilizada * mp.preco_unitario) as custo_subtotal
            FROM receitas r
            JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
            WHERE r.id_produto = %s AND r.id_subproduto IS NULL
            
            UNION ALL
            
            SELECT 
                r.id as id_vinculo,
                'subproduto' as tipo,
                sub.id as id_item,
                sub.nome as item, 
                r.quantidade_utilizada as qtd, 
                sub.unidade_medida as unidade,
                (r.quantidade_utilizada * COALESCE(sub.custo_producao_unitario, 0)) as custo_subtotal
            FROM receitas r
            JOIN subprodutos sub ON r.id_subproduto = sub.id
            WHERE r.id_produto = %s
        """
        cursor.execute(query_itens, (id_produto, id_produto))
        colunas = [desc[0] for desc in cursor.description]
        itens = [dict(zip(colunas, row)) for row in cursor.fetchall()]
        
        # 3. Cálculos Financeiros Integrados
        total_custo = sum(float(item['custo_subtotal'] or 0) for item in itens)
        preco_venda = float(produto[2] or 0)
        lucro = preco_venda - total_custo
        margem = (lucro / preco_venda * 100) if preco_venda > 0 else 0
        
        return render_template(
            "ficha_tecnica.html", 
            produto=produto, 
            itens=itens, 
            total=round(total_custo, 2), 
            lucro=round(lucro, 2), 
            margem=round(margem, 2)
        )
    except Exception as e:
        print(f"Erro na ficha técnica: {e}")
        flash(f"Erro ao carregar ficha técnica: {e}", "danger")
        return redirect("/estoque")
    finally:
        if con: con.close()


@app.route("/ficha-tecnica/editar-item/<int:id_produto>", methods=["POST"])
@login_required
def editar_item_ficha(id_produto):
    con = None
    try:
        id_vinculo = int(request.form["id_vinculo"])
        nova_qtd = float(request.form["quantidade"].replace(",", "."))
        
        con = conectar()
        cursor = con.cursor()
        
        # Atualiza a quantidade do ingrediente ou subproduto na tabela relacional receitas
        cursor.execute("""
            UPDATE receitas 
            SET quantidade_utilizada = %s 
            WHERE id = %s AND id_produto = %s
        """, (nova_qtd, id_vinculo, id_produto))
        
        con.commit()
        flash("Quantidade da receita ajustada com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao salvar alteração da ficha: {e}", "danger")
    finally:
        if con: con.close()
    return redirect(f"/ficha-tecnica/{id_produto}")


@app.route("/subprodutos/registrar-lote", methods=["POST"])
@login_required
def registrar_lote():
    con = None
    try:
        con = conectar()
        cursor = con.cursor()

        # Captura os dados enviados pelo modal do HTML
        nome_comercial = request.form.get("nome")
        preco_venda = request.form.get("preco")
        id_subproduto = request.form.get("id_subproduto")
        quantidade_lote = request.form.get("quantidade")

        # CASO 1: Ajuste dos dados básicos do Produto Final (Via botão Ajustar do loop de produtos)
        if nome_comercial and preco_venda:
            preco_venda = float(preco_venda.replace(",", "."))
            # Atualiza o último produto modificado ou adiciona filtro se tiver ID vindo no contexto.
            # Como o seu formulário não envia ID no loop, pegamos pelo nome comercial para atualizar o preço.
            cursor.execute("""
                UPDATE produtos 
                SET preco_venda = %s 
                WHERE nome = %s
            """, (preco_venda, nome_comercial))
            con.commit()
            flash(f"Produto '{nome_comercial}' atualizado com sucesso!", "success")

        # CASO 2: Entrada de Lote de Produção Avulsa (Via Modal de produção)
        elif id_subproduto and quantidade_lote:
            qtd = float(quantidade_lote.replace(",", "."))
            cursor.execute("""
                UPDATE subprodutos 
                SET quantidade_atual = COALESCE(quantidade_atual, 0) + %s 
                WHERE id = %s
            """, (qtd, id_subproduto))
            con.commit()
            flash("Lote de produção injetado com sucesso!", "success")
        
        else:
            flash("Dados insuficientes para processar a requisição.", "warning")

    except Exception as e:
        flash(f"Erro ao processar atualização no estoque: {e}", "danger")
    finally:
        if con: con.close()
    return redirect("/estoque")
# =========================================================
# PREVISÃO DE DEMANDA IA
# =========================================================
@app.route("/previsao-estoque")
def previsao_estoque():

    from modules.db import conectar

    con = None

    try:
        con = conectar()
        cur = con.cursor()

        # =====================================================
        # BUSCA TODAS MATÉRIAS-PRIMAS
        # =====================================================
        cur.execute("""
            SELECT
                id_materia_prima,
                nome,
                unidade_medida
            FROM materia_prima
            ORDER BY nome ASC
        """)

        materias = cur.fetchall()

        previsoes = []

        # =====================================================
        # LOOP MATÉRIAS-PRIMAS
        # =====================================================
        for materia in materias:

            id_mp = materia[0]
            nome_mp = materia[1]
            unidade = materia[2]

            # =====================================================
            # ESTOQUE ATUAL
            # =====================================================
            cur.execute("""
                SELECT
                    COALESCE(
                        SUM(
                            CASE
                                WHEN tipo_movimento IN ('entrada', 'ajuste')
                                    THEN quantidade
                                ELSE 0
                            END
                        ), 0
                    )
                    -
                    COALESCE(
                        SUM(
                            CASE
                                WHEN tipo_movimento = 'saida'
                                    THEN quantidade
                                ELSE 0
                            END
                        ), 0
                    )
                FROM movimentacao_estoque
                WHERE id_materia_prima = %s
            """, (id_mp,))

            estoque_atual = float(cur.fetchone()[0] or 0)

            # =====================================================
            # CONSUMO ÚLTIMOS 30 DIAS
            # =====================================================
            cur.execute("""
                SELECT
                    COALESCE(SUM(quantidade), 0)
                FROM movimentacao_estoque
                WHERE id_materia_prima = %s
                AND tipo_movimento = 'saida'
                AND data_movimentacao >= CURRENT_DATE - INTERVAL '30 days'
            """, (id_mp,))

            total_consumido = float(cur.fetchone()[0] or 0)

            # =====================================================
            # MÉDIA DIÁRIA
            # =====================================================
            media_diaria = total_consumido / 30 if total_consumido > 0 else 0

            # =====================================================
            # IA SIMPLES → TENDÊNCIA
            # =====================================================
            fator_tendencia = 1.15

            consumo_previsto_7d = round(
                media_diaria * 7 * fator_tendencia,
                2
            )

            consumo_previsto_15d = round(
                media_diaria * 15 * fator_tendencia,
                2
            )

            # =====================================================
            # DIAS RESTANTES
            # =====================================================
            if media_diaria > 0:
                dias_restantes = round(
                    estoque_atual / media_diaria,
                    1
                )
            else:
                dias_restantes = 999

            # =====================================================
            # NÍVEL DE RISCO
            # =====================================================
            if dias_restantes <= 2:
                risco = "CRÍTICO"

            elif dias_restantes <= 5:
                risco = "ALTO"

            elif dias_restantes <= 10:
                risco = "MODERADO"

            else:
                risco = "BAIXO"

            # =====================================================
            # SUGESTÃO DE COMPRA
            # =====================================================
            sugestao_compra = max(
                round(consumo_previsto_15d - estoque_atual, 2),
                0
            )

            # =====================================================
            # APPEND
            # =====================================================
            previsoes.append({

                "materia_prima": nome_mp,

                "estoque_atual": round(
                    estoque_atual,
                    2
                ),

                "unidade": unidade,

                "consumo_previsto": consumo_previsto_7d,

                "dias_restantes": dias_restantes,

                "media_diaria": round(
                    media_diaria,
                    2
                ),

                "consumo_15d": consumo_previsto_15d,

                "risco": risco,

                "sugestao_compra": sugestao_compra
            })

        # =====================================================
        # ORDENA POR RISCO
        # =====================================================
        previsoes.sort(
            key=lambda x: x["dias_restantes"]
        )

        return render_template(
            "previsao.html",
            previsoes=previsoes
        )

    except Exception as e:

        print(f"Erro previsão estoque: {e}")

        flash(
            f"Erro ao gerar previsão: {e}",
            "danger"
        )

        return redirect("/")

    finally:

        if con:
            con.close()



# =========================================================
# Sistema Fiscal
# =========================================================

@app.route("/financeiro")
@login_required
@acesso_requerido("financeiro")
def pagina_financeiro():
    dados = financeiro_operacional()

    return render_template(
        "financeiro.html",
        faturamento=dados["faturamento"],
        custo_insumos=dados["custo_insumos"],
        total_fixas=dados["total_fixas"],
        lucro_base=dados["lucro_base"]
    )

@app.route("/relatorio-financeiro")
@login_required
@acesso_requerido("financeiro")
def relatorio_financeiro():
    dados = relatorio_fiscal()

    return render_template(
        "relatorio_financeiro.html",
        regime_atual=dados["regime_atual"],
        faturamento=dados["faturamento"],
        lucro_atual=dados["lucro_atual"],
        imposto=dados["imposto_atual"],
        simulacoes=dados["simulacoes"]
    )
# =========================================================
# ROTA: FLUXO DE CAIXA
# =========================================================
@app.route("/fluxo-caixa")
@login_required
@acesso_requerido("financeiro")
def fluxo_caixa():
    try:
        # Por enquanto, vamos apenas abrir a página. 
        # Depois podemos buscar os dados reais de vendas e compras no banco.
        return render_template("fluxo_caixa.html")
    except Exception as e:
        print(f"Erro ao abrir fluxo de caixa: {e}")
        flash("Página de fluxo de caixa em desenvolvimento ou arquivo não encontrado.", "info")
        return redirect(url_for('dashboard'))
    
# =========================================================
# Gambiarras
# =========================================================
    

@app.route("/despesas", methods=["GET", "POST"])
@login_required
def despesas():
    if request.method == "POST":
        descricao = request.form["descricao"]
        valor = float(request.form["valor"])

        con = conectar()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO despesas (descricao, valor, data_despesa)
            VALUES (%s, %s, CURRENT_DATE)
        """, (descricao, valor))
        con.commit()
        con.close()

        flash("Despesa cadastrada com sucesso!", "success")
        return redirect("/despesas")

    # Comportamento GET
    con = conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT id_despesa, descricao, valor, TO_CHAR(data_despesa, 'DD/MM/YYYY')
        FROM despesas
        ORDER BY data_despesa DESC
    """)
    lista_despesas = cur.fetchall()
    con.close()

    # AJUSTE AQUI: Mudamos para despesa.html (singular) para bater com o nome do seu arquivo!
    return render_template("despesa.html", despesas=lista_despesas)


# =========================
# EXPORTAR PREVISÃO CSV
# =========================
@app.route("/exportar-previsao/csv")
@login_required
def exportar_previsao_csv():

    previsoes = estoque.previsao_demanda()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Matéria Prima",
        "Unidade",
        "Estoque Atual",
        "Consumo Médio Diário",
        "Consumo 7 Dias",
        "Consumo 15 Dias",
        "Dias Restantes",
        "Risco",
        "Sugestão Compra"
    ])

    for item in previsoes:

        writer.writerow([
            item["materia_prima"],
            item["unidade"],
            item["estoque_atual"],
            item["media_diaria"],
            item["consumo_previsto"],
            item["consumo_15d"],
            item["dias_restantes"],
            item["risco"],
            item["sugestao_compra"]
        ])

    response = make_response(output.getvalue())

    response.headers["Content-Disposition"] = \
        "attachment; filename=previsao_demanda.csv"

    response.headers["Content-type"] = "text/csv"

    return response


# =========================
# EXPORTAR PREVISÃO EXCEL
# =========================
@app.route("/exportar-previsao/excel")
@login_required
def exportar_previsao_excel():

    previsoes = estoque.previsao_demanda()

    df = pd.DataFrame(previsoes)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name='Previsao'
        )

    output.seek(0)

    return send_file(
        output,
        download_name="previsao_demanda.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =========================
# EXPORTAR PREVISÃO PDF
# =========================
@app.route("/exportar-previsao/pdf")
@login_required
def exportar_previsao_pdf():

    previsoes = estoque.previsao_demanda()

    buffer = io.BytesIO()

    pdf = canvas.Canvas(buffer, pagesize=letter)

    largura, altura = letter

    y = altura - 40

    pdf.setFont("Helvetica-Bold", 16)

    pdf.drawString(
        40,
        y,
        "Relatório de Previsão de Demanda"
    )

    y -= 40

    pdf.setFont("Helvetica", 10)

    for item in previsoes:

        linha = (
            f"{item['materia_prima']} | "
            f"Estoque: {item['estoque_atual']} | "
            f"Dias restantes: {item['dias_restantes']} | "
            f"Risco: {item['risco']}"
        )

        pdf.drawString(40, y, linha)

        y -= 20

        # NOVA PÁGINA
        if y < 40:

            pdf.showPage()

            y = altura - 40

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="previsao_demanda.pdf",
        mimetype="application/pdf"
    )



# =========================================================
# LISTAR SUBPRODUTOS (Calculando saldo em tempo real)
# =========================================================
def listar_subprodutos():
    con = None
    try:
        con = conectar()
        cur = con.cursor()

        # Calcula o saldo real olhando o histórico de movimentações da tabela modificada
        cur.execute("""
            SELECT 
                s.id_subproduto,
                s.nome,
                s.unidade_medida,
                s.estoque_minimo,
                s.preco_custo_unidade,
                COALESCE(SUM(CASE WHEN mov.tipo_movimento IN ('entrada', 'ajuste') THEN mov.quantidade ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'saida' THEN mov.quantidade ELSE 0 END), 0) as saldo
            FROM subprodutos s
            LEFT JOIN movimentacao_estoque mov ON s.id_subproduto = mov.id_subproduto
            WHERE s.ativo = 1
            GROUP BY s.id_subproduto, s.nome, s.unidade_medida, s.estoque_minimo, s.preco_custo_unidade
            ORDER BY s.nome ASC
        """)

        subprodutos = cur.fetchall()
        lista_final = []

        for s in subprodutos:
            saldo = float(s[5])
            status = "BAIXO" if saldo <= float(s[3]) else "OK"
            
            lista_final.append((
                s[0],               # id_subproduto
                s[1],               # nome
                s[2],               # unidade_medida
                float(s[3]),        # estoque_minimo
                saldo,              # saldo atual calculado
                status,             # status ("BAIXO" ou "OK")
                float(s[4])         # preco_custo_unidade
            ))

        return lista_final
    except Exception as e:
        print(f"Erro ao listar subprodutos: {e}")
        return []
    finally:
        if con:
            con.close()


# =========================================================
# CADASTRAR SUBPRODUTO / MATÉRIA-BASE
# =========================================================
def cadastrar_subproduto_banco(nome, unidade, estoque_minimo):
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        
        # O subproduto nasce sem preço e sem estoque. O estoque e custo entram quando houver produção!
        cur.execute("""
            INSERT INTO subprodutos (nome, unidade_medida, estoque_minimo)
            VALUES (%s, %s, %s)
        """, (nome, unidade, estoque_minimo))
        
        con.commit()
        return True
    except Exception as e:
        print(f"Erro ao cadastrar subproduto no banco: {e}")
        return False
    finally:
        if con:
            con.close()


# =========================================================
# VINCULAR RECEITA DO SUBPRODUTO (Ficha Técnica do Subproduto)
# =========================================================
def vincular_insumo_subproduto(id_subproduto, id_materia_prima, quantidade):
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        
        cur.execute("""
            INSERT INTO receitas_subprodutos (id_subproduto, id_materia_prima, quantidade_utilizada)
            VALUES (%s, %s, %s)
        """, (int(id_subproduto), int(id_materia_prima), float(quantidade)))
        
        con.commit()
        return True
    except Exception as e:
        print(f"Erro ao vincular insumo ao subproduto: {e}")
        return False
    finally:
        if con:
            con.close()


# =========================================================
# EXCLUIR SUBPRODUTO (Desativação Lógica)
# =========================================================
def excluir_subproduto_banco(id_subproduto):
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        
        # Em vez de deletar de vez e quebrar históricos, mudamos para inativo (ativo = 0)
        cur.execute("""
            UPDATE subprodutos 
            SET ativo = 0 
            WHERE id_subproduto = %s
        """, (id_subproduto,))
        
        con.commit()
        return True
    except Exception as e:
        print(f"Erro ao excluir subproduto do banco: {e}")
        return False
    finally:
        if con:
            con.close()
# =========================
# INICIALIZAÇÃO
# =========================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

