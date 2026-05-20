import os
import csv
import io
import json
import pandas as pd
from modules.normalizador_ia import encontrar_produto_similar
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from flask import Response
from datetime import datetime
from functools import wraps
from google import genai
from google.genai import types
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
from werkzeug.utils import secure_filename

from modules.ocr_notas import analisar_nota
from modules.previsao import prever_consumo_materia_prima
from modules.permissoes import acesso_requerido
from modules.usuarios import registrar_log_db
from modules.db import conectar
import psycopg2

# =========================
# APP
# =========================
client = genai.Client()
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
# TABELA LOGS (INICIALIZAÇÃO SEGURA)
# ========================================================
with app.app_context():
    try:
        # Usando 'with' gerenciamos a abertura e fechamento automático do cursor e da conexão
        with conectar() as conn:
            with conn.cursor() as cur:
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
        print("✔ Logs verificados com sucesso no banco de dados.")

    except Exception as e:
        # Evita derrubar a aplicação inteira se for apenas uma checagem de tabela
        print(f"❌ Erro crítico ao inicializar tabela de logs: {e}")

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
        # Sanitização básica de inputs
        username_form = request.form.get("username", "").strip().lower()
        senha_form = request.form.get("senha", "").strip()

        # Busca o usuário no banco
        usuario = usuarios.buscar_usuario(username_form)

        if not usuario:
            flash("Usuário ou senha incorretos.", "danger")
            return render_template("login.html"), 401

        # DESEMPACOTAMENTO RESILIENTE
        # Garante clareza total dos dados independente de manipulação interna do módulo
        try:
            id_user, username_db, senha_db, nivel_db, ativo = usuario[:5]
        except ValueError:
            print("❌ ERRO CRÍTICO: Estrutura da tabela de usuários não condiz com o desempacotamento.")
            flash("Erro interno no sistema de autenticação.", "danger")
            return render_template("login.html"), 500

        if int(ativo) == 0:
            flash("Esta conta foi bloqueada. Contate o administrador.", "danger")
            return render_template("login.html"), 403

        # Validação segura do Hash de senha
        if not check_password_hash(senha_db, senha_form):
            # Usamos a mesma mensagem genérica por boas práticas de segurança (evita mapeamento de usernames válidos)
            flash("Usuário ou senha incorretos.", "danger")
            return render_template("login.html"), 401

        # Criação do objeto de sessão do Flask-Login
        user_obj = User(id_user, username_db, nivel_db)
        login_user(user_obj)

        # Atualização do estado da sessão
        session["user_id"] = id_user
        session["nivel"] = nivel_db
        session["username"] = username_db

        registrar_log("LOGIN", "AUTH", f"Usuário '{username_db}' autenticado com sucesso")
        
        flash(f"Bem-vindo de volta, {username_db}!", "success")
        return redirect(url_for("dashboard"))

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
        # =====================================================
        # RESUMOS (Otimização de chamadas)
        # =====================================================
        resumo_diario = vendas.obter_resumo_periodo(1) or {"faturamento": 0, "total_vendas": 0, "lucro": 0}
        resumo_semanal = vendas.obter_resumo_periodo(7) or {"faturamento": 0, "total_vendas": 0, "lucro": 0}
        resumo_mensal = vendas.obter_resumo_periodo(30) or {"faturamento": 0, "total_vendas": 0, "lucro": 0}

        # =====================================================
        # ESTOQUE CRÍTICO (Filtro Inteligente e Seguro)
        # =====================================================
        capacidade = produtos.calcular_capacidade_geral() if hasattr(produtos, 'calcular_capacidade_geral') else []
        
        # Engenharia sênior: Se o seu módulo estoque já tiver um filtro nativo no banco, use-o.
        # Caso contrário, fazemos o fallback blindado contra erros de conversão de string/None.
        if hasattr(estoque, 'obter_itens_criticos'):
            criticos = estoque.obter_itens_criticos()
        else:
            insumos = estoque.listar_materia_prima() or []
            criticos = []
            for item in insumos:
                try:
                    # Evita quebra de tipo se o banco retornar Nulo ou String mal formatada
                    estoque_atual = float(item[4] if len(item) > 4 else 0)
                    estoque_minimo = float(item[3] if len(item) > 3 else 0)
                    if estoque_atual <= estoque_minimo:
                        criticos.append(item)
                except (ValueError, TypeError, IndexError):
                    continue

        return render_template(
            "dashboard.html",
            diario=resumo_diario,
            semana=resumo_semanal,
            mes=resumo_mensal,
            capacidade=capacidade,
            criticos=criticos
        )

    except Exception as e:
        print(f"❌ ERRO GRAVE NO DASHBOARD: {e}")
        # Estado de Fallback seguro para o usuário não ver uma tela de erro 500 desastrosa
        valores_vazios = {"faturamento": 0, "total_vendas": 0, "lucro": 0}
        return render_template(
            "dashboard.html",
            diario=valores_vazios,
            semana=valores_vazios,
            mes=valores_vazios,
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
        tipo_item = request.form.get("tipo_item")  # 'subproduto' ou 'produto'
        id_item_raw = request.form.get("id_item")
        quantidade_raw = request.form.get("quantidade", "").strip()

        # 1. Validação e conversão segura do ID
        if not id_item_raw or not id_item_raw.isdigit():
            flash("ID do item inválido ou não informado.", "danger")
            return redirect("/estoque")
        id_item = int(id_item_raw)

        # 2. Sanitização e conversão segura da Quantidade
        if not quantidade_raw:
            flash("Por favor, informe uma quantidade válida para a produção.", "warning")
            return redirect("/estoque")

        try:
            # Substitui a vírgula decimal e converte com segurança
            qtd = float(quantidade_raw.replace(",", "."))
        except ValueError:
            flash("A quantidade informada contém caracteres inválidos. Use apenas números.", "danger")
            return redirect("/estoque")

        # 3. Validação de Regra de Negócio (Quantidade não pode ser zerada ou negativa)
        if qtd <= 0:
            flash("A quantidade produzida deve ser maior do que zero.", "warning")
            return redirect("/estoque")

        # 4. Execução das Baixas e Entradas de Estoque
        if tipo_item == "subproduto":
            estoque.entrada_subproduto(id_item, qtd)
            registrar_log("PRODUCAO", "SUBPRODUTO", f"ID {id_item} | Qtd {qtd}")
        elif tipo_item == "produto":
            estoque.entrada_produto(id_item, qtd)
            registrar_log("PRODUCAO", "PRODUTO", f"ID {id_item} | Qtd {qtd}")
        else:
            flash("Tipo de item desconhecido para o registro de produção.", "danger")
            return redirect("/estoque")
            
        flash(f"Produção de {qtd} unidade(s) registrada com sucesso e insumos baixados!", "success")

    except Exception as e:
        print(f"❌ ERRO ROTA REGISTRAR PRODUÇÃO: {e}")
        flash(f"Erro interno ao processar produção no estoque: {e}", "danger")
        
    return redirect("/estoque")

# =====================================================================
# --- PAINEL DE ESTOQUE E EXCLUSÃO (MATEI OS PLURAIS E COLUNAS ERRADAS) ---
# =====================================================================

@app.route("/estoque", methods=["GET"])
@login_required
def estoque_painel():

    try:

        with conectar() as con:

            with con.cursor() as cur:

                # =====================================================
                # MATÉRIAS-PRIMAS
                # =====================================================

                cur.execute("""

                    SELECT 
                        m.id_materia_prima,
                        m.nome,
                        m.unidade_medida,
                        m.estoque_minimo,

                        COALESCE(
                            SUM(
                                CASE
                                    WHEN mov.tipo_movimento IN ('entrada', 'ajuste')
                                    THEN mov.quantidade
                                    ELSE 0
                                END
                            ), 0
                        )

                        -

                        COALESCE(
                            SUM(
                                CASE
                                    WHEN mov.tipo_movimento = 'saida'
                                    THEN mov.quantidade
                                    ELSE 0
                                END
                            ), 0
                        ) AS estoque_atual,

                        CASE
                            WHEN (
                                COALESCE(
                                    SUM(
                                        CASE
                                            WHEN mov.tipo_movimento IN ('entrada', 'ajuste')
                                            THEN mov.quantidade
                                            ELSE 0
                                        END
                                    ), 0
                                )

                                -

                                COALESCE(
                                    SUM(
                                        CASE
                                            WHEN mov.tipo_movimento = 'saida'
                                            THEN mov.quantidade
                                            ELSE 0
                                        END
                                    ), 0
                                )

                            ) <= m.estoque_minimo

                            THEN 'BAIXO'

                            ELSE 'OK'

                        END AS status,

                        COALESCE(m.preco_unitario, 0),

                        TO_CHAR(m.data_cadastro, 'DD/MM/YYYY')

                    FROM materia_prima m

                    LEFT JOIN movimentacao_estoque mov
                        ON m.id_materia_prima = mov.id_materia_prima

                    GROUP BY
                        m.id_materia_prima,
                        m.nome,
                        m.unidade_medida,
                        m.estoque_minimo,
                        m.preco_unitario,
                        m.data_cadastro

                    ORDER BY m.nome ASC

                """)

                materias = cur.fetchall()

                # =====================================================
                # SUBPRODUTOS
                # =====================================================

                cur.execute("""

                    SELECT
                        id_subproduto,
                        nome,
                        0 as estoque_atual,
                        preco_custo_unidade,
                        unidade_medida,
                        TO_CHAR(data_cadastro, 'DD/MM/YYYY')

                    FROM subprodutos

                    ORDER BY nome ASC

                """)

                subprodutos = cur.fetchall()

                # =====================================================
                # PRODUTOS FINAIS
                # =====================================================

                cur.execute("""

                    SELECT
                        id_produto,
                        nome,
                        preco_venda,
                        categoria,
                        0 as estoque_atual,
                        TO_CHAR(data_cadastro, 'DD/MM/YYYY')

                    FROM produtos

                    ORDER BY nome ASC

                """)

                produtos = cur.fetchall()

        return render_template(
            "estoque.html",
            materias=materias,
            subprodutos=subprodutos,
            produtos=produtos
        )

    except Exception as e:

        print(f"❌ ERRO GRAVE NO PAINEL ESTOQUE: {e}")

        flash(
            f"Não foi possível carregar os dados do painel de estoque: {e}",
            "danger"
        )

        return redirect("/")

@app.route("/estoque/balanco-diario")
@login_required
@acesso_requerido("estoque")
def balanco_diario_page():
    try:
        # 1. Filtro seguro de data via Query Param (?data=AAAA-MM-DD)
        data_param = request.args.get('data', '').strip()
        
        if data_param:
            hoje_str = data_param
            try:
                # Conversão robusta de exibição de data (ISO -> PT-BR)
                ano, mes, dia = hoje_str.split('-')
                data_exibicao = f"{dia}/{mes}/{ano}"
            except ValueError:
                data_exibicao = hoje_str
        else:
            hoje_str = datetime.now().strftime("%Y-%m-%d")
            data_exibicao = datetime.now().strftime("%d/%m/%Y")

        # 2. Coleta de dados dos módulos com fallback seguro
        lista_produtos = estoque.listar_produtos_finais() if hasattr(estoque, 'listar_produtos_finais') else (produtos.listar_todos() if 'produtos' in globals() else [])
        historico_vendas = estoque.listar_vendas() if hasattr(estoque, 'listar_vendas') else []
        
        # 3. OTIMIZAÇÃO SÊNIOR: Mapeia as vendas do dia selecionado em um Hash Map na memória
        # Isso reduz a complexidade de O(N*M) para O(N+M), salvando a CPU do seu Render.
        vendas_do_dia = {}
        for v in (historico_vendas or []):
            try:
                # Identifica dinamicamente se o registro de venda é dicionário ou objeto/tupla
                if isinstance(v, dict):
                    v_id = v.get('id_produto')
                    v_data = v.get('data')
                    v_qtd = v.get('quantidade', 0)
                elif hasattr(v, 'id_produto'):
                    v_id = v.id_produto
                    v_data = v.data
                    v_qtd = getattr(v, 'quantidade', 0)
                else:
                    v_id = v[2]
                    v_data = v[1]
                    v_qtd = v[3]

                # Normaliza a data da venda para comparação estrita de string
                v_data_str = v_data if isinstance(v, str) else v_data.strftime("%Y-%m-%d") if hasattr(v_data, 'strftime') else str(v_data)
                
                # Se a venda pertence à data filtrada, acumula no dicionário agrupando por ID do produto
                if hoje_str in v_data_str:
                    pid_str = str(v_id)
                    vendas_do_dia[pid_str] = vendas_do_dia.get(pid_str, 0) + int(v_qtd)
            except (IndexError, ValueError, TypeError, AttributeError):
                continue # Proteção contra linhas de dados corrompidas no histórico

        # 4. Construção consolidada do balanço diário
        balanco = []
        for p in (lista_produtos or []):
            try:
                id_produto = p[0]
                nome_produto = p[1]
                
                # Captura inteligente do saldo atual (sobra) tratando os índices de forma resiliente
                dado_sobrou = p[4] if len(p) > 4 else (p[3] if len(p) > 3 else 0)
                sobrou = int(dado_sobrou) if dado_sobrou is not None else 0
                
                # Busca instantânea no Hash Map de vendas que criamos acima
                vendido_hoje = vendas_do_dia.get(str(id_produto), 0)
                
                # Matemática reversa segura
                feito_hoje = sobrou + vendido_hoje
                
                balanco.append({
                    "id": id_produto,
                    "nome": nome_produto,
                    "feito": feito_hoje,
                    "vendido": vendido_hoje,
                    "sobrou": sobrou
                })
            except (IndexError, ValueError, TypeError):
                continue

        return render_template(
            "balanco_diario.html", 
            data_hoje=data_exibicao, 
            data_busca_atual=hoje_str, 
            datetime_hoje=datetime.now().strftime("%Y-%m-%d"),
            balanco=balanco
        )
        
    except Exception as e:
        print(f"❌ ERRO GRAVE NO BALANÇO DIÁRIO: {e}")
        flash(f"Erro interno ao processar o balanço diário: {e}", "danger")
        return redirect(url_for('estoque_page'))

# =====================================================================
# --- ROTA: ATUALIZAR PRODUTO (HIGIENIZAÇÃO E SEGURANÇA) ---
# =====================================================================
@app.route("/editar-produto/<int:id_produto>", methods=["POST"])
@login_required
def atualizar_produto(id_produto):
    try:
        nome = request.form.get("nome", "").strip()
        preco_raw = request.form.get("preco", "0").strip()

        if not nome:
            flash("O nome do produto não pode ficar em branco.", "warning")
            return redirect(url_for("estoque_page"))

        # Conversão segura de valores monetários vindos do formulário
        try:
            preco = float(preco_raw.replace(",", "."))
            if preco < 0:
                raise ValueError
        except ValueError:
            flash("Preço inválido informado. O valor deve ser um número positivo.", "danger")
            return redirect(url_for("estoque_page"))

        # Executa a atualização (Padrão mantido no módulo atual)
        sucesso = usuarios.update_produto(id_produto, nome, preco)

        if sucesso:
            registrar_log("ALTERAR", "PRODUTOS", f"Produto ID {id_produto} alterado para: {nome} | R$ {preco}")
            flash("Produto atualizado com sucesso!", "success")
        else:
            flash("Erro interno ao tentar atualizar o produto no banco de dados.", "danger")

    except Exception as e:
        print(f"❌ ERRO ROTA ATUALIZAR PRODUTO: {e}")
        flash(f"Erro inesperado: {e}", "danger")

    return redirect(url_for("estoque_page"))


# =====================================================================
# --- ROTA: ATUALIZAR MATÉRIA-PRIMA / INSUMO ---
# =====================================================================
@app.route("/editar-materia-prima/<int:id_mp>", methods=["POST"])
@login_required
def processar_edicao_mp(id_mp):
    try:
        nome = request.form.get("nome", "").strip()
        unidade = request.form.get("unidade", "").strip()
        preco_raw = request.form.get("preco_custo", "0").strip()
        quantidade_raw = request.form.get("quantidade", "0").strip()

        if not nome or not unidade:
            flash("Nome e Unidade de Medida são obrigatórios.", "warning")
            return redirect(url_for('estoque_page'))

        # Blindagem numérica contra falhas de digitação (Ex: '2,5' ou espaços vazios)
        try:
            preco = float(preco_raw.replace(",", "."))
            quantidade = float(quantidade_raw.replace(",", "."))
            if preco < 0 or quantidade < 0:
                raise ValueError
        except ValueError:
            flash("Valores numéricos de custo ou quantidade inválidos.", "danger")
            return redirect(url_for('estoque_page'))

        # Executa a atualização usando a função mapeada
        sucesso = usuarios.atualizar_materia_prima(id_mp, nome, preco, unidade, quantidade)

        if sucesso:
            registrar_log("ALTERAR", "MATERIA_PRIMA", f"Insumo ID {id_mp} alterado: {nome} | Estoque: {quantidade} {unidade}")
            flash("Matéria-prima atualizada com sucesso!", "success")
        else:
            flash("Erro ao tentar atualizar a matéria-prima no banco de dados.", "danger")

    except Exception as e:
        print(f"❌ ERRO ROTA EDITAR MATÉRIA-PRIMA: {e}")
        flash(f"Erro inesperado: {e}", "danger")

    return redirect(url_for('estoque_page'))



# =====================================================================
# CADASTRO PRODUTOS/MATÉRIA-PRIMA (CENTRAL)
# =====================================================================

# --- ROTA PRINCIPAL DA CENTRAL DE CADASTROS ---
@app.route("/cadastro")
@login_required
def render_cadastro():
    try:
        # Carrega dados essenciais tratando retornos nulos
        lista_produtos = produtos.listar_todos() or []
        lista_materias = estoque.listar_materia_prima() or []
        
        # Mantém verificação resiliente para o ecossistema de subprodutos
        lista_subprodutos = estoque.listar_subprodutos() if hasattr(estoque, 'listar_subprodutos') else []
        
        return render_template(
            "cadastro.html", 
            produtos=lista_produtos, 
            materias=lista_materias,
            subprodutos=lista_subprodutos or []
        )
    except Exception as e:
        print(f"❌ ERRO AO RENDERIZAR CADASTRO: {e}")
        flash("Erro ao carregar a central de cadastros. Tente novamente.", "danger")
        return redirect(url_for('dashboard'))


# --- AÇÃO: CADASTRAR MATÉRIA-PRIMA (INSUMOS) ---
@app.route("/cadastrar-mp", methods=["POST"])
@login_required
def cadastrar_mp():
    try:
        nome = request.form.get("nome", "").strip()
        unidade = request.form.get("unidade", "").strip()
        preco_raw = request.form.get("preco", "").strip()
        estoque_at_raw = request.form.get("estoque_atual", "").strip()
        estoque_min_raw = request.form.get("estoque_minimo", "").strip()
        
        if not nome or not unidade or not preco_raw:
            flash("Nome, Unidade e Preço são campos obrigatórios.", "warning")
            return redirect(url_for('render_cadastro'))
            
        try:
            preco = float(preco_raw.replace(",", "."))
            estoque_at = float(estoque_at_raw.replace(",", ".")) if estoque_at_raw else 0.0
            estoque_min = float(estoque_min_raw.replace(",", ".")) if estoque_min_raw else 0.0
            
            if preco < 0 or estoque_at < 0 or estoque_min < 0:
                raise ValueError
        except ValueError:
            flash("Valores numéricos inválidos ou negativos informados para o insumo.", "danger")
            return redirect(url_for('render_cadastro'))
        
        if estoque.cadastrar_materia(nome, unidade, preco, estoque_at, estoque_min):
            registrar_log("CADASTRO", "MATERIA_PRIMA", f"Insumo salvo: {nome} | Custo: R$ {preco}")
            flash(f"Insumo '{nome}' salvo com sucesso!", "success")
        else:
            flash("Erro interno ao persistir o insumo no banco.", "danger")
            
    except Exception as e:
        print(f"❌ ERRO ROTA CADASTRAR-MP: {e}")
        flash(f"Erro inesperado: {e}", "danger")
        
    return redirect(url_for('render_cadastro'))


# --- AÇÃO: CADASTRAR PRODUTO FINAL ---
@app.route("/cadastrar-produto", methods=["POST"])
@login_required
def cadastrar_produto_final():
    try:
        nome = request.form.get("nome", "").strip()
        preco_raw = request.form.get("preco", "").strip()
        categoria = request.form.get("categoria", "").strip()
        
        if not nome or not preco_raw:
            flash("Nome e Preço de Venda são obrigatórios.", "warning")
            return redirect(url_for('render_cadastro'))
            
        try:
            preco = float(preco_raw.replace(",", "."))
            if preco < 0:
                raise ValueError
        except ValueError:
            flash("O preço do produto deve ser um número válido e positivo.", "danger")
            return redirect(url_for('render_cadastro'))
            
        if produtos.cadastrar_produto(nome, preco, categoria):
            registrar_log("CADASTRO", "PRODUTO", f"Novo produto final: {nome} | Preço: R$ {preco}")
            flash(f"Produto '{nome}' cadastrado com sucesso!", "success")
        else:
            flash("Erro ao salvar produto final no banco de dados.", "danger")
            
    except Exception as e:
        print(f"❌ ERRO ROTA CADASTRAR-PRODUTO: {e}")
        flash(f"Erro nos dados inseridos: {e}", "danger")
        
    return redirect(url_for('render_cadastro'))


# --- AÇÃO: VINCULAR RECEITA (ENGENHARIA DA FICHA TÉCNICA) ---
@app.route("/vincular-receita", methods=["POST"])
@login_required
def vincular_receita():
    try:
        id_p = request.form.get("id_produto")
        id_m = request.form.get("id_materia_prima")
        quantidade_raw = request.form.get("quantidade", "").strip()
        
        if not id_p or not id_m or not quantidade_raw:
            flash("Selecione o Produto, o Insumo e informe a Quantidade.", "warning")
            return redirect(url_for('render_cadastro'))
            
        try:
            qtd = float(quantidade_raw.replace(",", "."))
            if qtd <= 0:
                raise ValueError
        except ValueError:
            flash("A quantidade utilizada na receita deve ser um valor maior do que zero.", "danger")
            return redirect(url_for('render_cadastro'))
        
        if produtos.vincular_insumo(id_p, id_m, qtd):
            registrar_log("CADASTRO", "FICHA_TECNICA", f"Vinculou MP ID {id_m} ao Prod ID {id_p} | Qtd: {qtd}")
            flash("Ingrediente/Insumo vinculado à receita!", "success")
        else:
            flash("Erro ao processar o vínculo no banco de dados.", "danger")
            
    except Exception as e:
        print(f"❌ ERRO ROTA VINCULAR-RECEITA: {e}")
        flash(f"Erro no vínculo: {e}", "danger")
        
    return redirect(url_for('render_cadastro'))


# =====================================================================
# SISTEMA DE EXCLUSÃO E AUDITORIA DE SEGURANÇA
# =====================================================================

# --- EXCLUIR PRODUTO ---
@app.route("/excluir-produto/<int:id_produto>", methods=["POST"])
@login_required
@acesso_requerido("estoque")  # Garante privilégio antes da deleção
def deletar_produto(id_produto):
    try:
        # CORREÇÃO SÊNIOR: Captura o usuário real conectado na sessão
        usuario_atual = session.get("username", "Desconhecido")
        
        # Tenta executar a exclusão através do módulo de produtos
        if produtos.excluir_produto(id_produto):
            registrar_log("DELETAR", "PRODUTOS", f"ID {id_produto} removido por '{usuario_atual}'")
            flash("Produto excluído com sucesso!", "success")
        else:
            flash("Não foi possível excluir o produto. Verifique se ele possui vínculos ativos.", "warning")
            
    except Exception as e:
        print(f"❌ ERRO ROTA EXCLUIR PRODUTO: {e}")
        flash(f"Erro interno ao tentar processar a exclusão: {e}", "danger")
        
    return redirect(url_for("render_cadastro"))


# =====================================================================
# --- EXCLUIR MATÉRIA-PRIMA (INSUMO - ADAPTADO E CORRIGIDO) ---
# =====================================================================
@app.route("/excluir-mp/<int:id_mp>", methods=["POST"])
@login_required
@acesso_requerido("estoque")
def deletar_mp(id_mp):
    """
    Seu endpoint que o HTML chama. Mantém a trava de segurança 
    do seu módulo estoque original.
    """
    try:
        usuario_atual = session.get("username", "Desconhecido")
        
        if estoque.excluir_materia(id_mp):
            if 'registrar_log' in globals():
                registrar_log("DELETAR", "MATERIA_PRIMA", f"Insumo ID {id_mp} removido por '{usuario_atual}'")
            flash("Matéria-prima excluída com sucesso!", "success")
        else:
            flash("Não foi possível remover o insumo. Certifique-se de que ele não faz parte de nenhuma receita ativa.", "warning")
            
    except Exception as e:
        print(f"❌ ERRO OPERACIONAL EXCLUIR MP: {e}")
        flash(f"Erro ao tentar deletar o insumo: {e}", "danger")
        
    try:
        return redirect(url_for("render_cadastro"))
    except Exception:
        return redirect("/estoque")


# =========================================================
# EXCLUIR / ESTORNAR VENDA
# =========================================================
@app.route("/deletar-venda/<int:id_venda>")
@login_required
@acesso_requerido("vendas")
def deletar_venda(id_venda):

    try:

        usuario_atual = session.get("username", "Desconhecido")

        # =====================================================
        # EXECUTA ESTORNO
        # =====================================================

        sucesso = vendas.excluir_venda(id_venda)

        if sucesso:

            registrar_log(
                "ESTORNO",
                "VENDAS",
                f"Venda ID {id_venda} cancelada por '{usuario_atual}'"
            )

            flash(
                "Venda estornada com sucesso e estoque devolvido!",
                "success"
            )

        else:

            flash(
                "Não foi possível localizar ou estornar esta venda.",
                "warning"
            )

    except Exception as e:

        print(f"❌ ERRO ROTA EXCLUIR VENDA: {e}")

        flash(
            f"Erro crítico no processamento do estorno: {e}",
            "danger"
        )

    # =====================================================
    # REDIRECIONA PARA VENDAS
    # =====================================================

    return redirect("/vendas")


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



# =====================================================================
# --- VENDAS (MANTENDO O SEU DICIONÁRIO DE DIRECIONAMENTO) ---
# =====================================================================
@app.route("/vendas")
@login_required
def pagina_vendas():

    try:

        # ==========================================
        # BUSCA PRODUTOS
        # ==========================================

        lista_produtos = produtos.buscar_produto_por_nome("")

        if not lista_produtos:
            lista_produtos = []

        # ==========================================
        # HISTÓRICO VENDAS
        # ==========================================

        historico = vendas.listar_vendas_recentes()

        if not historico:
            historico = []

        # ==========================================
        # RENDERIZA
        # ==========================================

        return render_template(
            "vendas.html",
            produtos=lista_produtos,
            historico_vendas=historico
        )

    except Exception as e:

        print(f"ERRO PAGINA VENDAS: {e}")

        flash("Erro ao carregar os dados de vendas.", "danger")

        return redirect("/")

@app.route("/vender", methods=["POST"])
@login_required
def vender():
    """Sua lógica de gravação e validação usando seus módulos."""
    try:
        id_p_raw = request.form.get("id_produto")
        qtd_raw = request.form.get("quantidade")

        if not id_p_raw or not qtd_raw:
            flash("Por favor, selecione um produto e informe a quantidade.", "warning")
            return redirect("/vendas")

        if not id_p_raw.isdigit() or not qtd_raw.isdigit():
            flash("Os dados enviados contêm caracteres inválidos.", "danger")
            return redirect("/vendas")

        id_p = int(id_p_raw)
        qtd = int(qtd_raw)

        if qtd <= 0:
            flash("A quantidade vendida deve ser maior que zero.", "warning")
            return redirect("/vendas")

        prods = produtos.buscar_produto_por_nome("") or []
        produto = next((p for p in prods if p[0] == id_p), None)

        if not produto:
            flash("Produto não encontrado no catálogo.", "danger")
            return redirect("/vendas")

        try:
            preco_unitario = float(produto[2])
            valor_total = preco_unitario * qtd
        except Exception:
            flash("Erro ao processar o preço do produto cadastrado.", "danger")
            return redirect("/vendas")

        # Validações dos seus arquivos internos
        estoque_ok = vendas.validar_estoque_suficiente(id_p, qtd)
        if not estoque_ok:
            flash("Estoque insuficiente para produzir essa venda.", "danger")
            return redirect("/vendas")

        usuario_atual = getattr(current_user, 'username', session.get('username', 'Desconhecido'))
        
        sucesso = vendas.registrar_venda(
            id_produto=id_p,
            quantidade=qtd,
            valor_total=valor_total,
            usuario=usuario_atual
        )

        if sucesso:
            if 'registrar_log' in globals():
                registrar_log("VENDA", "VENDAS", f"Produto ID {id_p} | Qtd {qtd} | Total R$ {valor_total:.2f}")
            flash("Venda registrada com sucesso!", "success")
        else:
            flash("Erro interno ao salvar a venda no banco de dados.", "danger")

    except Exception as e:
        print(f"❌ Erro crítico no processo de checkout de vendas: {e}")
        flash(f"Erro inesperado ao registrar a venda: {e}", "danger")

    return redirect("/vendas")

# =====================================================================
# --- INTERFACE DE AUDITORIA (VISUALIZAR LOGS) ---
# =====================================================================
@app.route("/auditoria")
@login_required
@acesso_requerido("auditoria")
def auditoria():
    try:
        usuario_filtro = request.args.get("usuario", "").strip()
        acao_filtro = request.args.get("acao", "").strip()
        modulo_filtro = request.args.get("modulo", "").strip()
        data_inicio = request.args.get("data_inicio", "").strip()
        data_fim = request.args.get("data_fim", "").strip()
        limite_raw = request.args.get("limite", "100")

        # Hardening e higienização estrita do limite
        try:
            limite = int(limite_raw)
            if limite <= 0: limite = 100
            if limite > 1000: limite = 1000
        except (ValueError, TypeError):
            limite = 100

        # Busca logs utilizando a função interna corrigida
        logs_data = listar_logs_auditoria_filtrado(
            limite=limite,
            usuario=usuario_filtro,
            acao=acao_filtro,
            modulo=modulo_filtro,
            data_inicio=data_inicio,
            data_fim=data_fim
        )

        return render_template(
            "auditoria.html",
            logs=logs_data,
            usuario_filtro=usuario_filtro,
            acao_filtro=acao_filtro,
            modulo_filtro=modulo_filtro,
            data_inicio=data_inicio,
            data_fim=data_fim,
            limite=limite
        )

    except Exception as e:
        print(f"❌ ERRO ROTA AUDITORIA: {e}")
        flash(f"Erro ao carregar painel de auditoria: {e}", "danger")
        return redirect(url_for('dashboard'))
# --- ENGINE DE FILTRAGEM SQL (CORRIGIDA COM AS COLUNAS REAIS) ---
def listar_logs_auditoria_filtrado(limite=100, usuario=None, acao=None, modulo=None, data_inicio=None, data_fim=None):
    # Correção Sênior: Alinhado estritamente com as colunas reais: id, usuario, acao, modulo, detalhe, data
    query = """
        SELECT usuario, acao, modulo, detalhe, data 
        FROM logs 
        WHERE 1=1
    """
    params = []

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
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
    except Exception as e:
        print(f"❌ Erro na consulta de logs filtrados: {e}")
        return []

# =========================================================
# REGISTRAR LOG DE AUDITORIA (MOTOR UNIFICADO)
# =========================================================
def registrar_log(acao, modulo, detalhe):
    """
    Grava uma ação de auditoria no banco de dados de forma isolada e segura.
    Garante o fechamento da conexão mesmo se o insert falhar.
    """
    query = """
        INSERT INTO logs (usuario, acao, modulo, detalhe)
        VALUES (%s, %s, %s, %s)
    """
    try:
        # Captura o usuário logado de forma resiliente (Flask-Login ou Session)
        usuario_atual = "Sistema"
        if 'current_user' in globals() and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            usuario_atual = getattr(current_user, 'username', 'Desconhecido')
        elif 'session' in globals() and session.get("username"):
            usuario_atual = session.get("username")

        # Garante que a conexão abra, salve e feche sem travar o pool do Render
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (usuario_atual, acao, modulo, detalhe))
                conn.commit()

    except Exception as e:
        # Logamos no console do Render para você não perder o rastro do erro,
        # mas não travamos a experiência do usuário na tela por falha de log.
        print(f"❌ FALHA CRÍTICA AO GRAVAR LOG DE AUDITORIA: {e}")

# =====================================================================
# --- EXPORTAÇÃO DE BACKUP JSON (VERSÃO BLINDADA) ---
# =====================================================================
@app.route("/logs/exportar")
@login_required
@acesso_requerido("auditoria")
def exportar_logs():
    try:
        # Usa a função de listagem limitando o escopo
        logs_brutos = listar_logs_auditoria_filtrado(limite=1000)
        logs_formatados = []

        for log in (logs_brutos or []):
            try:
                # Segurança: Se o banco retornar tupla, desempacota por índice. Se objeto, evita quebra.
                u, a, m, d, dt = log[:5]
                logs_formatados.append({
                    "usuario": u,
                    "acao": a,
                    "modulo": m,
                    "detalhe": d,
                    "data": str(dt)
                })
            except (IndexError, TypeError, ValueError):
                continue

        json_output = json.dumps(logs_formatados, indent=4, ensure_ascii=False)

        # Registra a ação de segurança de forma dinâmica e resiliente
        if 'registrar_log' in globals():
            registrar_log("EXPORT_LOGS", "AUDITORIA", "Backup de logs exportado via JSON")
        elif 'usuarios' in globals() and hasattr(usuarios, 'registrar_log_db'):
            usuario_atual = getattr(current_user, 'username', 'Desconhecido')
            usuarios.registrar_log_db(usuario=usuario_atual, acao="EXPORT_LOGS", modulo="AUDITORIA", detalhe="Backup exportado")

        return Response(
            json_output,
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=auditoria_pupilos.json"}
        )

    except Exception as e:
        print(f"❌ ERRO EXPORTAR LOGS: {e}")
        flash(f"Erro ao exportar arquivo de auditoria: {e}", "danger")
        # Fallback inteligente: se a rota 'auditoria' não existir no seu app, joga pro dashboard ou home
        try:
            return redirect(url_for("auditoria"))
        except Exception:
            return redirect("/")

# =====================================================================
# --- ECOSSISTEMA DE GESTÃO DE EQUIPE / USUÁRIOS ---
# =====================================================================

@app.route("/equipe")
@login_required
def gerenciar_equipe():
    if session.get("nivel") not in ["admin", "socios"]:
        flash("Acesso negado!", "danger")
        return redirect(url_for("dashboard"))
    try:
        lista_usuarios = usuarios.listar_usuarios() or []
        return render_template("equipe.html", equipe=lista_usuarios)
    except Exception as e:
        print(f"❌ ERRO TELA EQUIPE: {e}")
        flash("Erro ao carregar listagem da equipe.", "danger")
        return redirect(url_for("dashboard"))


@app.route("/usuarios")
@login_required
def listar_usuarios():
    if session.get("nivel") not in ["admin", "socios"]:
        flash("Acesso negado!", "danger")
        return redirect(url_for("dashboard"))
    try:
        lista = usuarios.listar_usuarios() or []
        return render_template("usuarios.html", equipe=lista)
    except Exception as e:
        print(f"❌ ERRO LISTAR USUÁRIOS: {e}")
        flash("Erro ao carregar dados dos usuários.", "danger")
        return redirect(url_for("dashboard"))


@app.route("/criar-usuario", methods=["POST"])
@login_required
def criar_usuario():
    if session.get("nivel") != "admin":
        flash("Somente administradores podem criar novos usuários.", "danger")
        return redirect(url_for("listar_usuarios"))

    try:
        username = request.form.get("username", "").strip().lower()
        senha = request.form.get("senha", "").strip()
        nivel = request.form.get("nivel", "").strip().lower()

        if not username or not senha or not nivel:
            flash("Todos os campos de cadastro são obrigatórios.", "warning")
            return redirect(url_for("listar_usuarios"))

        if usuarios.criar_usuario(username, senha, nivel):
            registrar_log("CRIAR_USUARIO", "USUARIOS", f"Usuário criado: {username} | Nível: {nivel}")
            flash(f"Usuário '{username}' criado com sucesso!", "success")
        else:
            flash("Não foi possível criar o usuário. Nome de usuário já pode estar em uso.", "danger")

    except Exception as e:
        print(f"❌ ERRO AO CRIAR USUÁRIO: {e}")
        flash(f"Erro operacional: {e}", "danger")

    return redirect(url_for("listar_usuarios"))


@app.route("/toggle-usuario/<int:id_usuario>")
@login_required
def toggle_usuario(id_usuario):
    if session.get("nivel") != "admin":
        flash("Permissão insuficiente para alterar estados de contas.", "danger")
        return redirect(url_for("listar_usuarios"))

    try:
        usuario = usuarios.buscar_usuario_id(id_usuario)
        if not usuario:
            flash("Usuário alvo não foi localizado no sistema.", "warning")
            return redirect(url_for("listar_usuarios"))

        # Desempacotamento seguro baseado na tupla padrão de usuários do seu app
        ativo_atual = int(usuario[4]) if len(usuario) > 4 else 1
        novo_status = 0 if ativo_atual == 1 else 1

        if usuarios.alterar_status(id_usuario, novo_status):
            status_txt = "ativado" if novo_status == 1 else "desativado"
            registrar_log("ALTERAR_STATUS", "USUARIOS", f"Usuário ID {id_usuario} ({usuario[1]}) foi {status_txt}")
            flash(f"Conta do usuário {status_txt} com sucesso!", "success")
        else:
            flash("Falha ao atualizar o status do usuário no banco.", "danger")

    except Exception as e:
        print(f"❌ ERRO NO TOGGLE STATUS: {e}")
        flash(f"Erro interno de processamento: {e}", "danger")

    return redirect(url_for("listar_usuarios"))


@app.route("/usuarios/editar/<int:id_usuario>", methods=["POST"])
@login_required
def editar_usuario(id_usuario):
    if session.get("nivel") not in ["admin", "socios"]:
        flash("Acesso negado!", "danger")
        return redirect(url_for("dashboard"))

    nivel = request.form.get("nivel", "").strip().lower()
    nova_senha = request.form.get("nova_senha", "").strip()
    
    try:
        with conectar() as con:
            with con.cursor() as cur:
                if nova_senha:
                    senha_hash = generate_password_hash(nova_senha)
                    cur.execute("""
                        UPDATE usuarios 
                        SET nivel = %s, senha = %s 
                        WHERE id_usuario = %s
                    """, (nivel, senha_hash, id_usuario))
                else:
                    cur.execute("""
                        UPDATE usuarios 
                        SET nivel = %s 
                        WHERE id_usuario = %s
                    """, (nivel, id_usuario))
                con.commit()
                
        flash("Dados cadastrais atualizados com sucesso!", "success")
        registrar_log("EDIÇÃO", "USUARIOS", f"Alterou dados do perfil ID {id_usuario}")
        
    except Exception as e:
        print(f"❌ ERRO COMPLETO EDITAR USUÁRIO: {e}")
        flash(f"Erro ao processar atualização no banco de dados: {e}", "danger")
        
    return redirect(url_for('listar_usuarios'))


# --- CONTROLADORES ADICIONAIS DE ROTEAMENTO INTERNO ---
@app.route("/admin/config")
@login_required
@acesso_requerido("usuarios")
def area_admin():
    try:
        lista_usuarios = usuarios.listar_usuarios() or []
        return render_template(
            "admin_panel.html",
            total_usuarios=len(lista_usuarios),
            usuarios=lista_usuarios
        )
    except Exception as e:
        print(f"❌ ERRO PAINEL ADMIN: {e}")
        flash("Erro ao acessar configurações administrativas.", "danger")
        return redirect(url_for("dashboard"))


@app.route("/cadastro-central")
@login_required
def cadastro_central():
    return redirect(url_for("render_cadastro"))

# =====================================================================
# --- CENTRAL DE IMPORTAÇÕES (AUDITADO E ADAPTADO) ---
# =====================================================================
@app.route("/importacoes")
@login_required
@acesso_requerido("vendas")
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

        # Registro de Log unificado e blindado usando o username real
        usuario_atual = getattr(current_user, 'username', session.get('username', 'Desconhecido'))
        registrar_log(
            acao="IMPORT_IFOOD", 
            modulo="VENDAS", 
            detalhe=f"Importação iniciada por '{usuario_atual}': {arquivo.filename}"
        )

        # O pipeline do Pandas (pd.read_excel/csv) rodará aqui sobre a variável 'arquivo'
        
        flash(f"Arquivo '{arquivo.filename}' recebido com sucesso! O processamento foi registrado.", "success")
        
    except Exception as e:
        print(f"❌ Erro na rota de importação iFood: {e}")
        flash(f"Erro crítico na importação: {e}", "danger")
        
    return redirect(url_for("central_importacoes"))


# =====================================================================
# --- INTERFACE DA FICHA TÉCNICA E ENGENHARIA DE CUSTOS ---
# =====================================================================
@app.route("/ficha-tecnica/<int:id_produto>")
@login_required
def ficha_tecnica(id_produto):
    try:
        query_produto = """
            SELECT id_produto, nome, preco_venda 
            FROM produtos 
            WHERE id_produto = %s
        """
        
        query_itens = """
            SELECT
                r.id_receita as id_vinculo,
                'materia_prima' as tipo,
                mp.id_materia_prima as id_item,
                mp.nome as item,
                r.quantidade_utilizada as qtd,
                mp.unidade_medida as unidade,
                (r.quantidade_utilizada * COALESCE(mp.preco_unitario, 0)) as custo_subtotal
            FROM receitas r
            JOIN materia_prima mp ON r.id_materia_prima = mp.id_materia_prima
            WHERE r.id_produto = %s AND r.id_subproduto IS NULL

            UNION ALL

            SELECT
                r.id_receita as id_vinculo,
                'subproduto' as tipo,
                sub.id_subproduto as id_item,
                sub.nome as item,
                r.quantidade_utilizada as qtd,
                sub.unidade_medida as unidade,
                (r.quantidade_utilizada * COALESCE(sub.preco_custo_unidade, 0)) as custo_subtotal
            FROM receitas r
            JOIN subprodutos sub ON r.id_subproduto = sub.id_subproduto
            WHERE r.id_produto = %s AND r.id_subproduto IS NOT NULL
        """

        # Executa as consultas sob gerência estrita de contexto (fecha o banco sozinho)
        with conectar() as con:
            with con.cursor() as cursor:
                cursor.execute(query_produto, (id_produto,))
                produto = cursor.fetchone()

                if not produto:
                    flash("Produto não encontrado no catálogo!", "danger")
                    return redirect(url_for("estoque_page") if "estoque_page" in globals() else "/estoque")

                produto_lista = [produto[0], produto[1], float(produto[2] or 0)]

                cursor.execute(query_itens, (id_produto, id_produto))
                colunas = [desc[0] for desc in cursor.description]
                itens = [dict(zip(colunas, row)) for row in cursor.fetchall()]

        # Processamento matemático dos indicadores financeiros
        total_custo = sum(float(item["custo_subtotal"] or 0) for item in itens)
        preco_venda = float(produto_lista[2] or 0)
        lucro = preco_venda - total_custo
        margem = (lucro / preco_venda) * 100 if preco_venda > 0 else 0

        return render_template(
            "ficha_tecnica.html",
            produto=produto_lista,
            itens=itens,
            total=round(total_custo, 2),
            lucro=round(lucro, 2),
            margem=round(margem, 2)
        )

    except Exception as e:
        print(f"❌ ERRO GRAVE FICHA TÉCNICA (ID PROD {id_produto}): {e}")
        flash(f"Erro ao processar dados da ficha técnica: {e}", "danger")
        return redirect(url_for("estoque_page") if "estoque_page" in globals() else "/estoque")


@app.route("/ficha-tecnica/editar-item/<int:id_produto>", methods=["POST"])
@login_required
def editar_item_ficha(id_produto):
    try:
        id_vinculo_raw = request.form.get("id_vinculo")
        quantidade_raw = request.form.get("quantidade", "0").strip()

        if not id_vinculo_raw:
            flash("Vínculo de ingrediente inválido.", "warning")
            return redirect(f"/ficha-tecnica/{id_produto}")

        try:
            id_vinculo = int(id_vinculo_raw)
            nova_qtd = float(quantidade_raw.replace(",", "."))
            if nova_qtd < 0: raise ValueError
        except ValueError:
            flash("A quantidade digitada precisa ser um número positivo.", "danger")
            return redirect(f"/ficha-tecnica/{id_produto}")

        with conectar() as con:
            with con.cursor() as cursor:
                cursor.execute("""
                    UPDATE receitas 
                    SET quantidade_utilizada = %s 
                    WHERE id_receita = %s AND id_produto = %s
                """, (nova_qtd, id_vinculo, id_produto))
                con.commit()
                
        registrar_log("ALTERAR", "FICHA_TECNICA", f"Ajustou qtd do vinculo ID {id_vinculo} no produto ID {id_produto} para {nova_qtd}")
        flash("Quantidade da receita ajustada com sucesso!", "success")
        
    except Exception as e:
        print(f"❌ ERRO AO EDITAR ITEM DA FICHA: {e}")
        flash(f"Erro ao salvar alteração da ficha técnica: {e}", "danger")
        
    return redirect(f"/ficha-tecnica/{id_produto}")


# =====================================================================
# --- AJUSTE DE PREÇOS E ENTRADA DE LOTES AVULSOS ---
# =====================================================================
@app.route("/subprodutos/registrar-lote", methods=["POST"])
@login_required
def registrar_lote():
    try:
        nome_comercial = request.form.get("nome", "").strip()
        preco_venda_raw = request.form.get("preco", "").strip()
        id_subproduto_raw = request.form.get("id_subproduto")
        quantidade_lote_raw = request.form.get("quantidade", "").strip()

        with conectar() as con:
            with con.cursor() as cursor:
                
                # CASO 1: Atualização rápida de Preço de Venda do Produto Final
                if nome_comercial and preco_venda_raw:
                    try:
                        preco_venda = float(preco_venda_raw.replace(",", "."))
                        if preco_venda < 0: raise ValueError
                    except ValueError:
                        flash("Preço de venda inválido.", "danger")
                        return redirect(url_for("estoque_page") if "estoque_page" in globals() else "/estoque")

                    cursor.execute("""
                        UPDATE produtos 
                        SET preco_venda = %s 
                        WHERE nome = %s
                    """, (preco_venda, nome_comercial))
                    con.commit()
                    
                    registrar_log("ALTERAR", "PRODUTOS", f"Preço de '{nome_comercial}' ajustado para R$ {preco_venda:.2f}")
                    flash(f"Preço do produto '{nome_comercial}' atualizado com sucesso!", "success")

                # CASO 2: Entrada manual de lote/produção de Subproduto
                elif id_subproduto_raw and quantidade_lote_raw:
                    try:
                        id_subproduto = int(id_subproduto_raw)
                        qtd = float(quantidade_lote_raw.replace(",", "."))
                        if qtd < 0: raise ValueError
                    except ValueError:
                        flash("Quantidade de lote informada é inválida.", "danger")
                        return redirect(url_for("estoque_page") if "estoque_page" in globals() else "/estoque")

                    # CORREÇÃO SÊNIOR: Ajustado de 'id' para a coluna correta 'id_subproduto' de acordo com criar_banco.py
                    cursor.execute("""
                        UPDATE subprodutos 
                        SET quantidade_atual = COALESCE(quantidade_atual, 0) + %s 
                        WHERE id_subproduto = %s
                    """, (qtd, id_subproduto))
                    con.commit()
                    
                    registrar_log("ESTOQUE", "SUBPRODUTOS", f"Injetou lote de {qtd} unidades no Subproduto ID {id_subproduto}")
                    flash("Lote de produção injetado e somado ao estoque com sucesso!", "success")
                
                else:
                    flash("Dados insuficientes ou campos vazios para processar a requisição.", "warning")

    except Exception as e:
        print(f"❌ ERRO ROTA REGISTRAR LOTE: {e}")
        flash(f"Erro operacional ao atualizar registros: {e}", "danger")
        
    return redirect(url_for("estoque_page") if "estoque_page" in globals() else "/estoque")



# =====================================================================
# --- SCANNER INTELIGENTE (VISÃO COMPUTACIONAL & IA DO GEMINI) ---
# =====================================================================

# Nota: Certifique-se de ter importado a SDK no topo do arquivo principal:
# from google import genai
# client = genai.Client()  # Certifique-se de que a variável GEMINI_API_KEY está configurada no Render

@app.route("/estoque/escanear-inteligente", methods=["POST"])
@login_required
def escanear_inteligente():
    try:
        # CASO 1: Captura rápida por Código de Barras
        codigo_enviado = request.form.get("codigo_barras")
        
        if codigo_enviado:
            with conectar() as con:
                with con.cursor() as cursor:
                    cursor.execute("SELECT id_produto, nome FROM produtos WHERE codigo_barras = %s", (codigo_enviado,))
                    produto = cursor.fetchone()
            
            if produto:
                return jsonify({"status": "sucesso", "acao": "adicionar", "id_produto": produto[0], "nome": produto[1]})
            else:
                return jsonify({"status": "novo", "acao": "cadastrar", "codigo_barras": codigo_enviado})

        # CASO 2: Processamento por Foto com Inteligência Artificial (Mecanismo Estável)
        if 'foto_produto' in request.files:
            file = request.files['foto_produto']
            if file.filename != '':
                imagem_bytes = file.read()
                
                # Chamada do modelo de forma nativa e compatível com o ecossistema do app
                response = client.models.generate_content(
                    model='gemini-3-flash',
                    contents=[
                        {
                            "mime_type": file.content_type or "image/jpeg",
                            "data": imagem_bytes
                        },
                        "Analise a imagem deste produto de estoque. Identifique o nome comercial exato do produto e a marca (se visível). Retorne APENAS o nome limpo do produto para preenchimento de formulário, sem introduções ou explicações adicionais."
                    ]
                )
                
                nome_identificado = response.text.strip() if response.text else ""
                
                if not nome_identificado:
                    return jsonify({"status": "erro", "mensagem": "A IA não conseguiu ler o produto da imagem."}), 422

                # Busca de similaridade no banco
                with conectar() as con:
                    with con.cursor() as cursor:
                        cursor.execute("SELECT id_produto, nome FROM produtos WHERE nome LIKE %s", (f"%{nome_identificado}%",))
                        produto_similar = cursor.fetchone()
                
                if produto_similar:
                    return jsonify({
                        "status": "sucesso", 
                        "acao": "adicionar", 
                        "id_produto": produto_similar[0], 
                        "nome": produto_similar[1],
                        "ia_detectou": nome_identificado
                    })
                else:
                    return jsonify({
                        "status": "novo", 
                        "acao": "cadastrar", 
                        "nome_sugerido": nome_identificado
                    })

        return jsonify({"status": "erro", "mensagem": "Nenhum dado ou imagem recebida."}), 400

    except Exception as e:
        print(f"❌ ERRO SCANNER INTELIGENTE IA: {e}")
        return jsonify({"status": "erro", "mensagem": f"Falha no processador de Visão Computacional: {str(e)}"}), 500



# =====================================================================
# --- PREVISÃO DE DEMANDA E CONSUMO INTELIGENTE (ESTOQUE CORRIGIDO) ---
# =====================================================================
@app.route("/previsao-estoque")
@login_required
def previsao_estoque():
    try:
        previsoes = []

        with conectar() as con:
            with con.cursor() as cur:
                
                # 1. Busca todas as matérias-primas cadastradas (tabela: materia_prima)
                cur.execute("""
                    SELECT id_materia_prima, nome, unidade_medida 
                    FROM materia_prima 
                    ORDER BY nome ASC
                """)
                materias = cur.fetchall() or []

                # 2. Processamento analítico de cada matéria-prima
                for materia in materias:
                    id_mp, nome_mp, unidade = materia

                    # Cálculo do saldo real atualizado
                    cur.execute("""
                        SELECT
                            COALESCE(SUM(CASE WHEN tipo_movimento IN ('entrada', 'ajuste') THEN quantidade ELSE 0 END), 0) -
                            COALESCE(SUM(CASE WHEN tipo_movimento = 'saida' THEN quantidade ELSE 0 END), 0)
                        FROM movimentacao_estoque
                        WHERE id_materia_prima = %s
                    """, (id_mp,))
                    estoque_atual = float(cur.fetchone()[0] or 0)

                    # CORREÇÃO CRÍTICA: data_movimento em vez de data_movimentacao
                    cur.execute("""
                        SELECT COALESCE(SUM(quantidade), 0)
                        FROM movimentacao_estoque
                        WHERE id_materia_prima = %s
                          AND tipo_movimento = 'saida'
                          AND data_movimento >= CURRENT_DATE - INTERVAL '30 days'
                    """, (id_mp,))
                    total_consumido = float(cur.fetchone()[0] or 0)

                    # Seu Motor Matemático Preditivo intacto
                    media_diaria = total_consumido / 30.0 if total_consumido > 0 else 0.0
                    fator_tendencia = 1.15

                    consumo_previsto_7d = round(media_diaria * 7 * fator_tendencia, 2)
                    consumo_previsto_15d = round(media_diaria * 15 * fator_tendencia, 2)

                    if media_diaria > 0:
                        dias_restantes = round(estoque_atual / media_diaria, 1)
                    else:
                        dias_restantes = 999.0

                    if dias_restantes <= 2:
                        risco = "CRÍTICO"
                    elif dias_restantes <= 5:
                        risco = "ALTO"
                    elif dias_restantes <= 10:
                        risco = "MODERADO"
                    else:
                        risco = "BAIXO"

                    sugestao_compra = max(round(consumo_previsto_15d - estoque_atual, 2), 0.0)

                    previsoes.append({
                        "materia_prima": nome_mp,
                        "estoque_atual": round(estoque_atual, 2),
                        "unidade": unidade,
                        "consumo_previsto": consumo_previsto_7d,
                        "dias_restantes": dias_restantes,
                        "media_diaria": round(media_diaria, 2),
                        "consumo_15d": consumo_previsto_15d,
                        "risco": risco,
                        "sugestao_compra": sugestao_compra
                    })

        previsoes.sort(key=lambda x: x["dias_restantes"])
        return render_template("previsao.html", previsoes=previsoes)

    except Exception as e:
        print(f"❌ ERRO MOTOR DE PREVISÃO DE ESTOQUE: {e}")
        flash(f"Não foi possível processar a previsão de demandas: {e}", "danger")
        return redirect(url_for("dashboard") if "dashboard" in globals() else "/")

# =====================================================================
# --- SISTEMA FISCAL E GESTÃO FINANCEIRA ---
# =====================================================================

# =========================================================
# SISTEMA FISCAL (ROTAS DEFINITIVAS)
# =========================================================

@app.route("/financeiro")
@login_required
@acesso_requerido("financeiro")
def pagina_financeiro():
    try:
        # Se as funções estiverem dentro de um arquivo importado como 'financeiro', 
        # mude a linha abaixo para: dados = financeiro.financeiro_operacional()
        dados = financeiro_operacional()

        return render_template(
            "financeiro.html",
            faturamento=dados["faturamento"],
            custo_insumos=dados["custo_insumos"],
            total_fixas=dados["total_fixas"],
            lucro_base=dados["lucro_base"]
        )
    except Exception as e:
        print(f"❌ Erro na rota /financeiro: {e}")
        flash(f"Erro ao carregar painel financeiro: {e}", "danger")
        return redirect("/")


@app.route("/relatorio-financeiro")
@login_required
@acesso_requerido("financeiro")
def relatorio_financeiro():
    try:
        # Se as funções estiverem dentro de um arquivo importado como 'financeiro', 
        # mude a linha abaixo para: dados = financeiro.relatorio_fiscal()
        dados = relatorio_fiscal()

        return render_template(
            "relatorio_financeiro.html",
            regime_atual=dados["regime_atual"],
            faturamento=dados["faturamento"],
            lucro_atual=dados["lucro_atual"],
            imposto=dados["imposto_atual"],
            simulacoes=dados["simulacoes"]
        )
    except Exception as e:
        print(f"❌ Erro na rota /relatorio-financeiro: {e}")
        flash(f"Erro ao carregar relatório fiscal: {e}", "danger")
        return redirect("/")


@app.route("/fluxo-caixa")
@login_required
@acesso_requerido("financeiro")
def fluxo_caixa():
    try:
        return render_template("fluxo_caixa.html")
    except Exception as e:
        print(f"❌ Erro ao abrir template fluxo de caixa: {e}")
        flash("Interface de fluxo de caixa não localizada ou em desenvolvimento.", "warning")
        return redirect("/")
    
# =====================================================================
# --- GESTÃO DE DESPESAS E MANUTENÇÃO DO BANCO ---
# =====================================================================

@app.route("/despesas", methods=["GET", "POST"])
@login_required
@acesso_requerido("financeiro") # Protegendo a rota com o nível de acesso correto
def despesas():
    if request.method == "POST":
        try:
            descricao = request.form.get("descricao", "").strip()
            valor_raw = request.form.get("valor", "0").strip()

            if not descricao:
                flash("A descrição da despesa não pode estar vazia.", "warning")
                return redirect("/despesas")

            # Sanitização de string para float de forma resiliente
            try:
                valor = float(valor_raw.replace(",", "."))
                if valor <= 0: raise ValueError
            except ValueError:
                flash("O valor digitado para a despesa é inválido.", "danger")
                return redirect("/despesas")

            # Executa o insert de forma isolada e segura
            with conectar() as con:
                with con.cursor() as cur:
                    cur.execute("""
                        INSERT INTO despesas (descricao, valor, data_despesa)
                        VALUES (%s, %s, CURRENT_DATE)
                    """, (descricao, valor))
                    con.commit()

            registrar_log("CADASTRAR", "DESPESAS", f"Cadastrou despesa '{descricao}' no valor de R$ {valor:.2f}")
            flash("Despesa cadastrada com sucesso!", "success")
            
        except Exception as e:
            print(f"❌ Erro ao salvar despesa: {e}")
            flash(f"Erro operacional ao salvar despesa: {e}", "danger")
            
        return redirect("/despesas")

    # Comportamento GET (Busca de dados protegida)
    try:
        with conectar() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT id_despesa, descricao, valor, TO_CHAR(data_despesa, 'DD/MM/YYYY')
                    FROM despesas
                    ORDER BY data_despesa DESC
                """)
                lista_despesas = cur.fetchall() or []
    except Exception as e:
        print(f"❌ Erro ao listar despesas: {e}")
        flash("Não foi possível carregar o histórico de despesas.", "danger")
        lista_despesas = []

    # Mantendo o redirecionamento exato para o seu arquivo singular despesa.html
    return render_template("despesa.html", despesas=lista_despesas)


    
# =====================================================================
# --- EXPORTAR PREVISÃO CSV (COMPATÍVEL COM EXCEL WINDOWS) ---
# =====================================================================
@app.route("/exportar-previsao/csv")
@login_required
def exportar_previsao_csv():
    try:
        # Reaproveita a função de cálculo que ajustamos no bloco anterior
        # Se ela estiver no próprio app.py, chame direto. Se estiver em módulo, use financeiro.financeiro_operacional()
        if 'relatorio_fiscal' in globals():
            # Pegamos os dados base através do motor matemático que já lê o banco
            dados_base = relatorio_fiscal()
            previsoes = dados_base.get("simulacoes", []) # ou o dicionário mapeado da sua lista de matérias-primas
        else:
            # Fallback de segurança buscando a função que criamos para as matérias-primas
            # Caso você tenha isolado a função de previsão de matérias:
            from modules.financeiro import financeiro_operacional 
            # Como segurança, se não achar a lista, calculamos uma lista de fallback ou usamos a função global
            previsoes = [] 
            
        # Caso precise re-executar o bloco exato de previsão de matérias-primas (do passo 1):
        # Vamos garantir que os dados venham estruturados.
        if not previsoes:
            # Puxamos uma simulação rápida ou redirecionamos se estiver vazio
            flash("Nenhum dado de previsão localizado para exportação no momento.", "warning")
            return redirect("/")

        output = io.StringIO()
        # O segredo sênior: escrevemos o BOM de UTF-8 para o Excel do Windows não quebrar os acentos
        output.write('\ufeff') 
        writer = csv.writer(output, delimiter=';') # Ponto e vírgula é o padrão mais amigável no Brasil

        writer.writerow([
            "Matéria-Prima", "Unidade", "Estoque Atual", 
            "Consumo Médio Diário", "Consumo 7 Dias", "Consumo 15 Dias", 
            "Dias Restantes", "Nível de Risco", "Sugestão de Compra"
        ])

        for item in previsoes:
            writer.writerow([
                item.get("materia_prima", "N/A"),
                item.get("unidade", "un"),
                str(item.get("estoque_atual", 0.0)).replace('.', ','),
                str(item.get("media_diaria", 0.0)).replace('.', ','),
                str(item.get("consumo_previsto", 0.0)).replace('.', ','),
                str(item.get("consumo_15d", 0.0)).replace('.', ','),
                str(item.get("dias_restantes", 0.0)).replace('.', ','),
                item.get("risco", "BAIXO"),
                str(item.get("sugestao_compra", 0.0)).replace('.', ',')
            ])

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=previsao_demanda.csv"
        response.headers["Content-type"] = "text/csv; charset=utf-8-sig"
        return response

    except Exception as e:
        print(f"❌ ERRO EXPORTAR CSV: {e}")
        flash(f"Falha ao gerar arquivo CSV: {e}", "danger")
        return redirect("/")


# =====================================================================
# --- EXPORTAR PREVISÃO EXCEL (FORMATADO E PROFISSIONAL) ---
# =====================================================================
@app.route("/exportar-previsao/excel")
@login_required
def exportar_previsao_excel():
    try:
        # Puxando os dados reais calculados pelo sistema
        # Para este exemplo, simulamos o reuso da lista estruturada que você tem no sistema
        # Idealmente, substitua pela sua chamada real de dados de matéria-prima
        dados_excel = [] 
        
        if not dados_excel:
            flash("Dados de previsão indisponíveis para gerar planilha Excel.", "info")
            return redirect("/")

        df = pd.DataFrame(dados_excel)
        
        # Renomeia as colunas técnicas para um padrão estético de relatório comercial
        colunas_traduzidas = {
            "materia_prima": "Matéria-Prima",
            "unidade": "Unidade de Medida",
            "estoque_atual": "Estoque Atual",
            "media_diaria": "Consumo Diário",
            "consumo_previsto": "Previsão 7 Dias",
            "consumo_15d": "Previsão 15 Dias",
            "dias_restantes": "Autonomia (Dias)",
            "risco": "Classificação de Risco",
            "sugestao_compra": "Sugestão de Compra"
        }
        df = df.rename(columns=colunas_traduzidas)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Previsão de Estoque')
            
            # Auto-ajuste de largura de colunas (Toque Sênior para não cortar texto no Excel)
            workbook = writer.book
            worksheet = writer.sheets['Previsão de Estoque']
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output.seek(0)
        return send_file(
            output,
            download_name="previsao_demanda.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        print(f"❌ ERRO EXPORTAR EXCEL: {e}")
        flash(f"Falha ao processar planilha Excel: {e}", "danger")
        return redirect("/")


# =====================================================================
# --- EXPORTAR PREVISÃO PDF (PROTEGIDO CONTRA QUEBRA DE TEXTO) ---
# =====================================================================
@app.route("/exportar-previsao/pdf")
@login_required
def exportar_previsao_pdf():
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        # Dados de exemplo baseados na estrutura matemática do seu estoque
        lista_previsoes = [] 

        if not lista_previsoes:
            flash("Não há dados de previsão disponíveis para exportação em PDF.", "info")
            return redirect("/")

        buffer = io.BytesIO()
        # Inicializa o documento com margens seguras
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elementos = []

        styles = getSampleStyleSheet()
        style_titulo = ParagraphStyle(
            'TituloRelatorio',
            parent=styles['Heading1'],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#1A237E'), # Azul Escuro Corporativo
            spaceAfter=15
        )
        
        style_texto = ParagraphStyle('TextoTabela', parent=styles['Normal'], fontSize=9, leading=12)
        style_header = ParagraphStyle('HeaderTabela', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.white, fontName="Helvetica-Bold")

        # Cabeçalho do PDF
        elementos.append(Paragraph("Relatório de Previsão de Demanda e Risco de Estoque", style_titulo))
        elementos.append(Spacer(1, 10))

        # Montagem da Tabela Estruturada (Evita o problema do texto sumir da página)
        dados_tabela = [[
            Paragraph("Matéria-Prima", style_header),
            Paragraph("Estoque", style_header),
            Paragraph("Autonomia", style_header),
            Paragraph("Risco", style_header),
            Paragraph("Sugestão", style_header)
        ]]

        for item in lista_previsoes:
            # Mapeia as cores do risco visualmente
            risco_texto = item.get("risco", "BAIXO")
            cor_risco = colors.HexColor('#2E7D32') # Verde padrão
            if risco_texto == "CRÍTICO": cor_risco = colors.HexColor('#C62828') # Vermelho
            elif risco_texto == "ALTO": cor_risco = colors.HexColor('#EF6C00') # Laranja
            elif risco_texto == "MODERADO": cor_risco = colors.HexColor('#FBC02D') # Amarelo

            style_risco = ParagraphStyle('RiscoStyle', parent=style_texto, textColor=cor_risco, fontName="Helvetica-Bold")

            dados_tabela.append([
                Paragraph(item.get("materia_prima", "N/A"), style_texto),
                Paragraph(f"{item.get('estoque_atual', 0.0)} {item.get('unidade', '')}", style_texto),
                Paragraph(f"{item.get('dias_restantes', 0.0)} dias", style_texto),
                Paragraph(risco_texto, style_risco),
                Paragraph(f"{item.get('sugestao_compra', 0.0)}", style_texto)
            ])

        # Estilização profissional da tabela para o PDF
        tabela = Table(dados_tabela, colWidths=[160, 100, 90, 80, 90])
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A237E')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]) # Zebra effect
        ]))

        elementos.append(tabela)
        doc.build(elementos)
        
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name="previsao_demanda.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        print(f"❌ ERRO EXPORTAR PDF: {e}")
        flash(f"Falha ao gerar relatório em PDF: {e}", "danger")
        return redirect("/")


# =====================================================================
# --- GERENCIAMENTO DE SUBPRODUTOS (CÁLCULO E ESTOQUE EM TEMPO REAL) ---
# =====================================================================

def listar_subprodutos():
    try:
        with conectar() as con:
            with con.cursor() as cur:
                # Modificado: Adicionado COALESCE no preço de custo para evitar crash com valores nulos
                cur.execute("""
                    SELECT 
                        s.id_subproduto,
                        s.nome,
                        s.unidade_medida,
                        COALESCE(s.estoque_minimo, 0) as estoque_minimo,
                        COALESCE(s.preco_custo_unidade, 0.0) as preco_custo_unidade,
                        COALESCE(SUM(CASE WHEN mov.tipo_movimento IN ('entrada', 'ajuste') THEN mov.quantidade ELSE 0 END), 0) -
                        COALESCE(SUM(CASE WHEN mov.tipo_movimento = 'saida' THEN mov.quantidade ELSE 0 END), 0) as saldo
                    FROM subprodutos s
                    LEFT JOIN movimentacao_estoque mov ON s.id_subproduto = mov.id_subproduto
                    WHERE s.ativo = 1
                    GROUP BY s.id_subproduto, s.nome, s.unidade_medida, s.estoque_minimo, s.preco_custo_unidade
                    ORDER BY s.nome ASC
                """)

                subprodutos = cur.fetchall() or []
                lista_final = []

                for s in subprodutos:
                    # Proteção sênior: Conversão segura de dados prevenindo quebras por tipos incompatíveis
                    estoque_min = float(s[3]) if s[3] is not None else 0.0
                    saldo = float(s[5]) if s[5] is not None else 0.0
                    preco_custo = float(s[4]) if s[4] is not None else 0.0
                    
                    status = "BAIXO" if saldo <= estoque_min else "OK"
                    
                    lista_final.append((
                        s[0],           # id_subproduto
                        s[1],           # nome
                        s[2],           # unidade_medida
                        estoque_min,    # estoque_minimo
                        saldo,          # saldo atual calculado
                        status,         # status ("BAIXO" ou "OK")
                        preco_custo     # preco_custo_unidade tratada
                    ))

                return lista_final
    except Exception as e:
        print(f"❌ Erro crítico ao listar subprodutos: {e}")
        return []


def cadastrar_subproduto_banco(nome, unidade, estoque_minimo):
    try:
        # Validação simples de preenchimento para evitar lixo no banco
        if not nome or not str(nome).strip():
            return False

        with conectar() as con:
            with con.cursor() as cur:
                cur.execute("""
                    INSERT INTO subprodutos (nome, unidade_medida, estoque_minimo, ativo)
                    VALUES (%s, %s, %s, 1)
                """, (nome.strip(), unidade, float(estoque_minimo or 0)))
                con.commit()
                return True
    except Exception as e:
        print(f"❌ Erro ao cadastrar subproduto no banco: {e}")
        return False


def vincular_insumo_subproduto(id_subproduto, id_materia_prima, quantidade):
    try:
        with conectar() as con:
            with con.cursor() as cur:
                cur.execute("""
                    INSERT INTO receitas_subprodutos (id_subproduto, id_materia_prima, quantidade_utilizada)
                    VALUES (%s, %s, %s)
                """, (int(id_subproduto), int(id_materia_prima), float(quantidade)))
                con.commit()
                return True
    except Exception as e:
        print(f"❌ Erro ao vincular insumo ao subproduto: {e}")
        return False


def excluir_subproduto_banco(id_subproduto):
    try:
        with conectar() as con:
            with con.cursor() as cur:
                # Soft delete mantendo conformidade com histórico fiscal/vendas
                cur.execute("""
                    UPDATE subprodutos 
                    SET ativo = 0 
                    WHERE id_subproduto = %s
                """, (int(id_subproduto),))
                con.commit()
                return True
    except Exception as e:
        print(f"❌ Erro ao desativar subproduto do banco: {e}")
        return False
    


# =========================================================
# COMPRAS INTELIGENTES
# =========================================================

@app.route("/compras-inteligentes")
@login_required
@acesso_requerido("estoque")
def compras_inteligentes():
    return render_template("compras_inteligentes.html")

@app.route("/processar-nota", methods=["POST"])
@login_required
def processar_nota():
    import os, json, uuid
    
    foto = request.files.get("foto_nota")
    if not foto:
        flash("Nenhuma imagem enviada.", "danger")
        return redirect("/compras-inteligentes")

    # Cria pasta temp e salva
    if not os.path.exists("temp"): os.makedirs("temp")
    caminho_imagem = os.path.join("temp", f"{uuid.uuid4()}{os.path.splitext(foto.filename)[1]}")
    foto.save(caminho_imagem)

    try:
        # Chama a IA
        resposta = analisar_nota(caminho_imagem)
        resposta_limpa = resposta.replace("```json", "").replace("```", "").strip()
        itens = json.loads(resposta_limpa)
        
        # Remove a imagem após processar a IA
        if os.path.exists(caminho_imagem): os.remove(caminho_imagem)
        
        # Renderiza a página de conferência (resultado_nota.html)
        return render_template("resultado_nota.html", itens=itens)
        
    except Exception as e:
        print(f"ERRO PROCESSAR NOTA: {e}")
        flash("Erro ao processar a nota com a IA.", "danger")
        return redirect("/compras-inteligentes")
    


@app.route("/confirmar-nota", methods=["POST"])
@login_required
def confirmar_nota():
    total = int(request.form.get("total_itens"))
    
    with conectar() as conn:
        with conn.cursor() as cur:
            for i in range(total):
                # Pega os dados editados ou confirmados pelo formulário
                nome = request.form.get(f"nome_{i}")
                qtd = float(request.form.get(f"qtd_{i}"))
                preco = float(request.form.get(f"preco_{i}"))
                
                # 1. Busca se já existe
                cur.execute("SELECT id_materia_prima FROM materia_prima WHERE LOWER(nome) = LOWER(%s)", (nome,))
                materia = cur.fetchone()
                
                if materia:
                    id_materia = materia[0]
                    cur.execute("UPDATE materia_prima SET preco_unitario = %s WHERE id_materia_prima = %s", (preco, id_materia))
                else:
                    # Cria se não existir
                    cur.execute("INSERT INTO materia_prima (nome, unidade_medida, preco_unitario) VALUES (%s, 'UN', %s) RETURNING id_materia_prima", (nome, preco))
                    id_materia = cur.fetchone()[0]
                
                # 2. Registra a entrada no estoque
                cur.execute("""INSERT INTO movimentacao_estoque (id_materia_prima, tipo_movimento, quantidade, observacao, usuario) 
                               VALUES (%s, 'ENTRADA', %s, 'Importação confirmada via IA', %s)""", 
                            (id_materia, qtd, current_user.username))
        conn.commit()
        
    flash("Estoque atualizado com sucesso!", "success")
    return redirect("/estoque") # Altere para a rota que você usa para listar o estoque
# =========================
# INICIALIZAÇÃO
# =========================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

