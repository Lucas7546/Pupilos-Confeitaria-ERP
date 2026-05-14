import os
import io
import json
import pandas as pd

from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
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
            capacidade=[],
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
# CADASTRO PRODUTOS/MATERIA-PRIMA
# =========================
# --- ROTA PRINCIPAL DA CENTRAL DE CADASTROS ---
@app.route("/cadastro")
@login_required
def render_cadastro():
    try:
        # Carrega dados para preencher os selects da Ficha Técnica
        # Certifique-se que seus módulos 'produtos' e 'estoque' retornam listas
        lista_produtos = produtos.listar_todos() 
        lista_materias = estoque.listar_materia_prima()
        
        return render_template("cadastro.html", 
                               produtos=lista_produtos, 
                               materias=lista_materias)
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
    return render_template("vendas.html", produtos=produtos.buscar_produto_por_nome(""))




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
        return redirect(url_for('dashboard'))
    
    try:
        # Busca os últimos 100 logs
        logs_data = usuarios.listar_logs_auditoria(100)
        return render_template('auditoria.html', logs=logs_data)
    except Exception as e:
        flash(f"Erro ao carregar logs: {e}", "danger")
        return redirect(url_for('dashboard'))

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


# =========================================================
# GERENCIAR EQUIPE
# =========================================================
@app.route("/equipe")
@login_required
def gerenciar_equipe():

    if session.get("nivel") not in ["admin", "gerente"]:

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

    if session.get("nivel") not in ["admin", "gerente"]:

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
    nivel = request.form.get("nivel")
    nova_senha = request.form.get("nova_senha")
    
    con = None
    try:
        con = conectar()
        cur = con.cursor()
        
        if nova_senha and len(nova_senha.strip()) > 0:
            # Atualiza nível e senha
            senha_hash = generate_password_hash(nova_senha)
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
        registrar_log_db(current_user.username, "EDIÇÃO", "USUARIOS", f"Alterou dados do ID {id_usuario}")
        
    except Exception as e:
        if con: con.rollback()
        flash(f"Erro ao atualizar: {e}", "danger")
    finally:
        if con: con.close()
        
    return redirect(url_for('gerenciar_usuarios'))




# =========================================================
# PAINEL ADMIN
# =========================================================
@app.route("/admin/config")
@login_required
def area_admin():
    # Usando o current_user que é mais confiável com Flask-Login
    if current_user.nivel != "admin":
        flash("Acesso restrito ao administrador.", "danger")
        return redirect(url_for("dashboard"))

    try:
        # Busca a lista para contar
        lista = usuarios.listar_usuarios()
        total_usuarios = len(lista) if lista else 0

        return render_template(
            "admin_panel.html",
            total_usuarios=total_usuarios
        )
    except Exception as e:
        print(f"Erro painel admin: {e}")
        flash(f"Erro ao carregar painel: {e}", "danger")
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


@app.route("/ficha-tecnica/<int:id_produto>")
@login_required
def ficha_tecnica(id_produto):
    cursor = conn.cursor()
    
    # 1. Busca os dados básicos do produto
    cursor.execute("SELECT id, nome, preco FROM produtos WHERE id = %s", (id_produto,))
    produto = cursor.fetchone()
    
    if not produto:
        return "Produto não encontrado", 404

    # 2. Busca os ingredientes (itens da ficha técnica)
    # Aqui fazemos um JOIN para pegar o nome e o preço unitário da matéria-prima
    query_itens = """
        SELECT 
            mp.nome as item, 
            r.quantidade as qtd, 
            (r.quantidade * mp.preco) as custo_subtotal
        FROM receitas r
        JOIN materia_prima mp ON r.id_materia_prima = mp.id
        WHERE r.id_produto = %s
    """
    cursor.execute(query_itens, (id_produto,))
    # Transformamos em dicionário para facilitar o acesso no HTML i.item, i.qtd...
    colunas = [desc[0] for desc in cursor.description]
    itens = [dict(zip(colunas, row)) for row in cursor.fetchall()]
    
    # 3. Cálculos Financeiros
    total_custo = sum(item['custo_subtotal'] for item in itens)
    preco_venda = float(produto[2])
    lucro = preco_venda - total_custo
    
    # Margem de lucro (evita divisão por zero)
    margem = (lucro / preco_venda * 100) if preco_venda > 0 else 0
    
    return render_template(
        "ficha_tecnica.html", 
        produto=produto, 
        itens=itens, 
        total=total_custo, 
        lucro=lucro, 
        margem=margem
    )




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
# =========================
# INICIALIZAÇÃO
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)