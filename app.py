from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask import Flask, render_template, request, redirect, flash
from datetime import datetime
import json
import pandas as pd
import os
import io
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash
import modules.vendas as vendas
import modules.estoque as estoque
import modules.produtos as produtos
import modules.receitas as receitas
import sqlite3

app = Flask(__name__)

app.secret_key = "confeitaria_secreta_2026"

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = "login"

# ========================================================
# HISTÓRICO IFOOD
# ========================================================



historico_ifood = []
historico_importacoes = []
upload_temp = {}
# ========================================================
# LOGIN, LOG e SEGURANÇA
# ========================================================



LOG_FILE = "logs.json"

def salvar_log(dados):

    logs = []

    if os.path.exists(LOG_FILE):

        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read()

                if content:
                    logs = json.loads(content)

        except Exception as e:
            print(f"Erro ao ler log: {e}")
            logs = []

    logs.append(dados)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)

def carregar_logs():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                if content:
                    return json.loads(content)
        except:
            return []
    return []

def registrar_log(acao, modulo, detalhe="", usuario_manual=None):
    # 1. DEFINIR O USUÁRIO
    if usuario_manual:
        usuario_log = usuario_manual
    elif current_user.is_authenticated:
        usuario_log = current_user.id
    else:
        usuario_log = "anonimo"

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- PARTE A: SALVAR NO BANCO DE DADOS (Para a página de Auditoria) ---
    try:
        conexao = sqlite3.connect("data/confeitaria.db")
        cursor = conexao.cursor()
        cursor.execute("""
            INSERT INTO logs (usuario, acao, modulo, detalhe)
            VALUES (?, ?, ?, ?)
        """, (usuario_log, acao, modulo, detalhe))
        conexao.commit()
        conexao.close()
    except Exception as e:
        print(f"Erro ao salvar no Banco: {e}")

    # --- PARTE B: SALVAR NO JSON (Para a página de Logs/Arquivo) ---
    try:
        log_entry = {
            "data": agora,
            "usuario": usuario_log,
            "acao": acao,
            "modulo": modulo,
            "detalhe": detalhe
        }

        logs_atuais = []
        # Lê o que já existe no arquivo
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                try:
                    logs_atuais = json.load(f)
                except: logs_atuais = []

        # Adiciona o novo e salva de volta
        logs_atuais.append(log_entry)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs_atuais, f, indent=4, ensure_ascii=False)

    except Exception as e:
        print(f"Erro ao salvar no JSON: {e}")


class User(UserMixin):
    def __init__(self, id):
        self.id = id


usuarios = {
    "admin": {
        "senha": generate_password_hash("123456")
    }
}

@login_manager.user_loader
def load_user(user_id):

    return User(user_id)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        senha = request.form["senha"]

        usuario = usuarios.get(username)

        if usuario and check_password_hash(usuario["senha"], senha):
            user = User(username)
            login_user(user)

            # AJUSTE AQUI: Passamos o username diretamente para a função
            registrar_log(
                "LOGIN",
                "AUTH",
                f"Usuário {username} entrou no sistema",
                usuario_manual=username  # <--- Adicione isso
            )

            flash("Login realizado com sucesso!", "success")
            return redirect("/")

        else:
            flash("Usuário ou senha inválidos", "danger")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():

    registrar_log(
        "LOGOUT",
        "AUTH",
        f"Usuário {current_user.id} saiu"
    )

    logout_user()

    flash("Logout realizado", "info")

    return redirect("/login")


@app.route("/reset-senha", methods=["POST"])
@login_required
def reset_senha():

    nova_senha = request.form["senha"].strip()

    usuario = usuarios.get(current_user.id)

    if not usuario:
        flash("Usuário não encontrado", "danger")
        return redirect("/cadastro")

    if len(nova_senha) < 6:
        flash("Senha muito curta (mínimo 6)", "danger")
        return redirect("/cadastro")

    usuario["senha"] = generate_password_hash(nova_senha)

    registrar_log(
        "RESET SENHA",
        "AUTH",
        f"Usuário {current_user.id} alterou a senha"
    )

    flash("Senha atualizada com sucesso!", "success")

    return redirect("/cadastro")


@app.route("/recuperar-senha")
def recuperar_senha_aviso():
    return """
    <div style="background:#0f172a; color:white; height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; font-family:sans-serif;">
        <h2 style="color:#f59e0b;">Esqueceu sua senha?</h2>
        <p>Por questões de segurança, a recuperação automática está desativada.</p>
        <p>Solicite o reset ao administrador do sistema.</p>
        <br>
        <a href="/login" style="color:#f59e0b; text-decoration:none; border: 1px solid #f59e0b; padding: 10px 20px; border-radius: 8px;">Voltar para o Login</a>
    </div>
    """

@app.route("/logs")
@login_required
def ver_logs():
    logs_exibir = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                if content:
                    logs_exibir = json.loads(content)
        except Exception as e:
            print(f"Erro ao carregar logs para visualização: {e}")

    # Passamos os logs lidos do arquivo, invertidos (mais novos primeiro)
    return render_template("logs.html", logs=reversed(logs_exibir))

def obter_ultimos_logs(limite=10):
    conexao = sqlite3.connect("data/confeitaria.db")
    cursor = conexao.cursor()
    # Busca os logs mais recentes primeiro
    cursor.execute("SELECT * FROM logs ORDER BY data DESC LIMIT ?", (limite,))
    logs = cursor.fetchall()
    conexao.close()
    return logs

@app.route('/auditoria')
@login_required
def auditoria():
    try:
        conexao = sqlite3.connect("data/confeitaria.db")
        # ESTA LINHA É OBRIGATÓRIA para o HTML funcionar com log['coluna']
        conexao.row_factory = sqlite3.Row 
        cursor = conexao.cursor()
        
        # Selecionamos as colunas e ordenamos pelo ID mais novo
        cursor.execute("""
            SELECT usuario, acao, modulo, detalhe, data 
            FROM logs 
            ORDER BY id_log DESC 
            LIMIT 100
        """)
        
        logs_data = cursor.fetchall()
        conexao.close()
        
        # Enviamos para o auditoria.html
        return render_template('auditoria.html', logs=logs_data)
        
    except Exception as e:
        print(f"❌ Erro ao carregar auditoria: {e}")
        # Retorna uma lista vazia para não quebrar a página em caso de erro
        return render_template('auditoria.html', logs=[])
# ========================================================
# 1. DASHBOARD
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
# 2. ESTOQUE (ATUALIZADO COM LOG + EDIT)
# ========================================================

@app.route("/estoque")
@login_required
def pagina_estoque():

    try:
        dados = estoque.listar_materia_prima()

        registrar_log(
            "ACESSO",
            "ESTOQUE",
            f"Usuário acessou o estoque"
        )

        return render_template(
            "estoque.html",
            materias=dados
        )

    except Exception as e:
        flash(f"Erro ao carregar estoque: {e}", "danger")
        return redirect("/")


@app.route("/compras")
@login_required
def pagina_compras():

    lista_materias = estoque.listar_materia_prima()

    return render_template(
        "compras.html",
        materias=lista_materias
    )


@app.route("/registrar-compra", methods=["POST"])
@login_required
def registrar_compra():

    try:

        id_mp = int(request.form["id_materia_prima"])

        qtd = float(
            request.form["quantidade"].replace(",", ".")
        )

        preco_total = float(
            request.form["preco_total"].replace(",", ".")
        )

        if qtd <= 0 or preco_total <= 0:
            flash("A quantidade deve ser maior que zero.", "warning")
            return redirect("/compras")

        preco_unitario = preco_total / qtd

        # EXECUÇÃO
        estoque.entrada_estoque(id_mp, qtd)
        estoque.atualizar_preco_mp(id_mp, preco_unitario)

        # LOG
        registrar_log(
            "COMPRA / ENTRADA ESTOQUE",
            "ESTOQUE",
            f"ID {id_mp} | qtd {qtd} | preco unit {preco_unitario:.2f}"
        )

        flash("Estoque e preços atualizados!", "success")

        return redirect("/estoque")

    except Exception as e:
        flash(f"Erro ao registrar compra: {e}", "danger")
        return redirect("/compras")


@app.route("/editar-estoque/<int:id_mp>", methods=["POST"])
@login_required
def editar_estoque(id_mp):

    try:
        novo_estoque = float(request.form["estoque"].replace(",", "."))

        estoque.ajustar_estoque(id_mp, novo_estoque)

        registrar_log(
            "EDIT ESTOQUE",
            "ESTOQUE",
            f"ID {id_mp} novo estoque {novo_estoque}"
        )

        flash("Estoque atualizado com sucesso!", "success")

        return redirect("/estoque")

    except Exception as e:
        flash(f"Erro ao editar estoque: {e}", "danger")
        return redirect("/estoque")
# ========================================================
# 3. CADASTROS
# ========================================================

@app.route("/cadastro")
@login_required
def pagina_cadastro():

    lista_produtos = produtos.buscar_produto_por_nome("")

    lista_materias = estoque.listar_materia_prima()

    return render_template(
        "cadastro.html",
        produtos=lista_produtos,
        materias=lista_materias
    )

@app.route("/cadastrar-mp", methods=["POST"])
@login_required
def cadastrar_mp():

    try:

        nome = request.form["nome"]

        unidade = request.form["unidade"]

        estoque_inicial = float(
            request.form["estoque_atual"].replace(",", ".")
        )

        preco = float(
            request.form["preco"].replace(",", ".")
        )

        minimo = float(
            request.form["estoque_minimo"].replace(",", ".")
        )

        ok = estoque.cadastrar_materia_prima(
            nome,
            unit=unidade,
            min_estoque=minimo,
            preco=preco
        )

        if ok:

            materias = estoque.listar_materia_prima()

            id_mp = [
                m[0] for m in materias if m[1] == nome
            ][0]

            estoque.entrada_estoque(
                id_mp,
                estoque_inicial
            )

            flash(
                f"{nome} cadastrado com sucesso!",
                "success"
            )

        else:

            flash(
                "Item já cadastrado.",
                "danger"
            )

        return redirect("/estoque")

    except Exception as e:

        flash(f"Erro: {e}", "danger")

        return redirect("/cadastro")

@app.route("/cadastrar-produto", methods=["POST"])
@login_required
def cadastrar_produto():

    try:

        nome = request.form["nome"]

        preco = float(
            request.form["preco"].replace(",", ".")
        )

        categoria = request.form["categoria"]

        produtos.cadastrar_produto(
            nome,
            preco,
            categoria
        )

        flash(
            f"Produto {nome} criado com sucesso!",
            "success"
        )

        return redirect("/cadastro")

    except Exception as e:

        flash(
            f"Erro ao cadastrar produto: {e}",
            "danger"
        )

        return redirect("/cadastro")

@app.route("/vincular-receita", methods=["POST"])
@login_required
def vincular_receita():

    try:

        id_prod = request.form["id_produto"]

        id_mp = request.form["id_materia_prima"]

        qtd = float(
            request.form["quantidade"].replace(",", ".")
        )

        receitas.cadastrar_receita(
            id_prod,
            id_mp,
            qtd
        )

        flash(
            "Ingrediente vinculado!",
            "success"
        )

        return redirect("/cadastro")

    except Exception as e:

        flash(f"Erro: {e}", "danger")

        return redirect("/cadastro")



# ========================================================
# 4. VENDAS
# ========================================================

@app.route("/vendas")
@login_required
def pagina_vendas():

    lista_produtos = produtos.buscar_produto_por_nome("")

    return render_template(
        "vendas.html",
        produtos=lista_produtos
    )


@app.route("/vender", methods=["POST"])
@login_required
def vender():

    try:

        id_p = int(request.form["id_produto"])
        qtd = int(request.form["quantidade"])

        if qtd <= 0:
            flash("Quantidade deve ser maior que zero.", "danger")
            return redirect("/vendas")

        lista = produtos.buscar_produto_por_nome("")

        produto_info = next(
            (p for p in lista if p[0] == id_p),
            None
        )

        if not produto_info:
            flash("Produto não encontrado.", "danger")
            return redirect("/vendas")

        preco_venda = produto_info[2]

        sucesso, mensagem = vendas.vender_produto(
            id_p,
            qtd,
            preco_venda
        )

        # LOG PROFISSIONAL
        if sucesso:

            registrar_log(
                "VENDA REALIZADA",
                "VENDAS",
                f"Produto ID {id_p} | qtd {qtd} | valor unit {preco_venda}"
            )

            flash(mensagem, "success")

        else:

            registrar_log(
                "VENDA NEGADA",
                "VENDAS",
                f"Produto ID {id_p} | qtd {qtd} | motivo: {mensagem}"
            )

            flash(mensagem, "danger")

        return redirect("/vendas")

    except ValueError:
        flash("Dados inválidos na venda.", "danger")
        return redirect("/vendas")

    except Exception as e:
        flash(f"Erro na venda: {e}", "danger")
        return redirect("/vendas")


# ========================================================
# 5. IFOOD
# ========================================================

@app.route("/importacoes")
@login_required
def central_importacoes():

    return render_template(
        "central_importacoes.html",
        historico_ifood=historico_ifood,
        historico_importacoes=historico_importacoes
    )


@app.route("/importar-ifood", methods=["POST"])
@login_required
def importar_ifood():

    try:

        arquivo = request.files["arquivo"]

        if not arquivo:
            flash("Nenhum arquivo enviado.", "danger")
            return redirect("/importacoes")

        # leitura segura
        if arquivo.filename.endswith(".csv"):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)

        produtos_sistema = produtos.buscar_produto_por_nome("")

        total_importado = 0
        valor_total = 0

        for _, row in df.iterrows():

            try:

                nome_produto = str(row["Produto"]).strip()
                quantidade = int(row["Quantidade"])
                valor = float(row["Valor"])

                produto = next(
                    (p for p in produtos_sistema if p[1].lower() == nome_produto.lower()),
                    None
                )

                if produto:

                    id_produto = produto[0]

                    vendas.vender_produto(
                        id_produto,
                        quantidade,
                        valor
                    )

                    total_importado += 1
                    valor_total += valor

            except Exception:
                # ignora linha quebrada sem parar sistema
                continue

        # histórico
        historico_ifood.insert(0, {

            "arquivo": arquivo.filename,
            "pedidos": total_importado,
            "valor": valor_total,
            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status": "Importado"

        })

        # LOG PROFISSIONAL
        registrar_log(
            "IMPORTAÇÃO IFOOD",
            "VENDAS",
            f"{total_importado} pedidos | valor total {valor_total:.2f} | arquivo {arquivo.filename}"
        )

        flash(
            f"{total_importado} pedidos importados com sucesso!",
            "success"
        )

        return redirect("/importacoes")

    except Exception as e:

        flash(f"Erro ao importar iFood: {e}", "danger")
        return redirect("/importacoes")

# ========================================================
# 6. PRECIFICAÇÃO
# ========================================================

@app.route("/precificacao")
@login_required
def pagina_precificacao():

    lista_produtos = produtos.buscar_produto_por_nome("")

    tabela_precos = []

    for p in lista_produtos:

        id_p, nome, preco_atual = p

        cenarios = produtos.calcular_cenarios_preco(
            id_p,
            preco_atual
        )

        tabela_precos.append({

            "id": id_p,

            "nome": nome,

            "atual": cenarios["atual"],

            "equilibio": cenarios["ponto_equilibrio"],

            "sugerido": cenarios["lucro_30"],

            "alerta": cenarios["atual"] < cenarios["ponto_equilibrio"]

        })

    return render_template(
        "precificacao.html",
        tabela=tabela_precos
    )

# ========================================================
# 7. FINANCEIRO
# ========================================================

@app.route("/financeiro")
@login_required
def pagina_financeiro():

    faturamento_mes = vendas.obter_resumo_periodo(
        dias=30
    )["faturamento"]

    custo_insumos = vendas.obter_custo_total_vendas(
        dias=30
    )

    despesas_fixas = vendas.listar_despesas(
        dias=30
    )

    total_fixas = sum([d[2] for d in despesas_fixas])

    lucro_real = (
        faturamento_mes
        - custo_insumos
        - total_fixas
    )

    return render_template(
        "financeiro.html",
        faturamento=faturamento_mes,
        custo_insumos=custo_insumos,
        despesas=despesas_fixas,
        total_fixas=total_fixas,
        lucro_real=lucro_real
    )

@app.route("/lancar-despesa", methods=["POST"])
@login_required
def lancar_despesa():

    try:

        descricao = request.form["descricao"]

        valor = float(
            request.form["valor"].replace(",", ".")
        )

        categoria = request.form["categoria"]

        vendas.registrar_despesa(
            descricao,
            valor,
            categoria
        )

        flash(
            "Despesa registrada!",
            "success"
        )

        return redirect("/financeiro")

    except Exception as e:

        flash(
            f"Erro ao lançar despesa: {e}",
            "danger"
        )

        return redirect("/financeiro")
    


@app.route("/importar-estrutura", methods=["POST"])
@login_required
def importar_estrutura():
    try:

        arquivo = request.files["arquivo"]

        if arquivo.filename.endswith(".csv"):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)

        total_produtos = 0

        produtos_existentes = produtos.buscar_produto_por_nome("")
        materias_existentes = estoque.listar_materia_prima()

        for _, row in df.iterrows():

            produto_nome = str(row["Produto"]).strip().lower()
            categoria = str(row["Categoria"]).strip().lower()
            ingrediente = str(row["Ingrediente"]).strip().lower()
            unidade = str(row["Unidade"]).strip().lower()

            quantidade = float(str(row["Quantidade"]).replace(",", ".").strip())

            produto_existente = next(
                (p for p in produtos_existentes if p[1].strip().lower() == produto_nome),
                None
            )

            if not produto_existente:

                produtos.cadastrar_produto(
                    produto_nome.title(),
                    0,
                    categoria.title()
                )

                produtos_existentes = produtos.buscar_produto_por_nome("")

                produto_existente = next(
                    (p for p in produtos_existentes if p[1].strip().lower() == produto_nome),
                    None
                )

                total_produtos += 1

            mp_existente = next(
                (m for m in materias_existentes if m[1].strip().lower() == ingrediente),
                None
            )

            if not mp_existente:

                estoque.cadastrar_materia_prima(
                    ingrediente.title(),
                    unit=unidade,
                    min_estoque=0,
                    preco=0
                )

                materias_existentes = estoque.listar_materia_prima()

                mp_existente = next(
                    (m for m in materias_existentes if m[1].strip().lower() == ingrediente),
                    None
                )

            receita_existente = receitas.listar_ingredientes_por_produto(
                produto_existente[0]
            )

            ja_existe = next(
                (r for r in receita_existente if r[0] == mp_existente[0]),
                None
            )

            if not ja_existe:

                receitas.cadastrar_receita(
                    produto_existente[0],
                    mp_existente[0],
                    quantidade
                )

        historico_importacoes.insert(0, {
            "arquivo": arquivo.filename,
            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status": "Importado"
        })

        flash(
            f"Estrutura importada com sucesso! {total_produtos} produtos criados.",
            "success"
        )

        return redirect("/importacoes")

    except Exception as e:
        flash(f"Erro ao importar estrutura: {e}", "danger")
        return redirect("/importacoes")   
    


# ========================================================
# PREVIA 
# ========================================================



@app.route("/preview-importacao", methods=["POST"])
@login_required
def preview_importacao():

    try:
        arquivo = request.files["arquivo"]

        if not arquivo:
            flash("Arquivo inválido", "danger")
            return redirect("/importacoes")

        # salva conteúdo em memória (SESSION SEGURA)
        content = arquivo.read()

        session["arquivo_importacao"] = {
            "nome": arquivo.filename,
            "dados": content.decode("latin1")
        }

        if arquivo.filename.endswith(".csv"):
            df = pd.read_csv(io.StringIO(content.decode("latin1")))
        else:
            df = pd.read_excel(io.BytesIO(content))

        produtos_existentes = produtos.buscar_produto_por_nome("")
        materias_existentes = estoque.listar_materia_prima()

        novos_produtos = set()
        novas_mps = set()

        for _, row in df.iterrows():

            p = str(row["Produto"]).strip().lower()
            m = str(row["Ingrediente"]).strip().lower()

            if not any(px[1].lower() == p for px in produtos_existentes):
                novos_produtos.add(p)

            if not any(mx[1].lower() == m for mx in materias_existentes):
                novas_mps.add(m)

        return render_template(
            "preview_importacao.html",
            novos_produtos=len(novos_produtos),
            novas_mps=len(novas_mps),
            receitas=len(df)
        )

    except Exception as e:
        flash(f"Erro no preview: {e}", "danger")
        return redirect("/importacoes")



@app.route("/confirmar-importacao", methods=["POST"])
@login_required
def confirmar_importacao():

    try:

        dados = session.get("arquivo_importacao")

        if not dados:
            flash("Arquivo expirado. Envie novamente.", "danger")
            return redirect("/importacoes")

        content = dados["dados"]

        df = pd.read_csv(io.StringIO(content)) if dados["nome"].endswith(".csv") else pd.read_excel(io.BytesIO(content.encode("latin1")))

        produtos_existentes = produtos.buscar_produto_por_nome("")
        materias_existentes = estoque.listar_materia_prima()

        for _, row in df.iterrows():

            produto_nome = str(row["Produto"]).strip().lower()
            ingrediente = str(row["Ingrediente"]).strip().lower()
            unidade = str(row["Unidade"]).strip().lower()
            quantidade = float(str(row["Quantidade"]).replace(",", "."))

            produto = next((p for p in produtos_existentes if p[1].lower() == produto_nome), None)

            if not produto:
                produtos.cadastrar_produto(produto_nome.title(), 0, "geral")
                produtos_existentes = produtos.buscar_produto_por_nome("")
                produto = next((p for p in produtos_existentes if p[1].lower() == produto_nome), None)

            mp = next((m for m in materias_existentes if m[1].lower() == ingrediente), None)

            if not mp:
                estoque.cadastrar_materia_prima(
                    ingrediente.title(),
                    unit=unidade,
                    min_estoque=0,
                    preco=0
                )
                materias_existentes = estoque.listar_materia_prima()
                mp = next((m for m in materias_existentes if m[1].lower() == ingrediente), None)

            receitas_existente = receitas.listar_ingredientes_por_produto(produto[0])

            if not any(r[0] == mp[0] for r in receitas_existente):

                receitas.cadastrar_receita(
                    produto[0],
                    mp[0],
                    quantidade
                )

        session.pop("arquivo_importacao", None)

        flash("Importação concluída com sucesso!", "success")
        return redirect("/importacoes")

    except Exception as e:
        flash(f"Erro na importação: {e}", "danger")
        return redirect("/importacoes")
    

# ========================================================
# AJUSTES PRECISOS
# ========================================================

    










# ========================================================
# SERVIDOR
# ========================================================

if __name__ == "__main__":

    # garante pasta data
    if not os.path.exists("data"):
        os.makedirs("data")

    app.run(
        host="0.0.0.0",
        port=5000
    )