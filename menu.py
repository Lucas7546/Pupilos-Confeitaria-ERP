import modules.estoque as estoque
import modules.produtos as produtos
import modules.receitas as receitas
import modules.vendas as vendas
import modules.utilidades as util

# =========================
# MENU PRINCIPAL
# =========================
def iniciar_menu():

    while True:

        util.limpar_tela()

        print("\n=== SISTEMA CONFEITARIA ===")
        print("1 - Cadastrar matéria-prima")
        print("2 - Listar matéria-prima")
        print("3 - Entrada de estoque")
        print("4 - Saída de estoque")
        print("5 - Ver estoque atual")
        print("6 - Cadastrar produto")
        print("7 - Comprar matéria-prima")
        print("8 - Ver alerta de estoque")
        print("9 - Vender produto")
        print("10 - Relatório financeiro")
        print("11 - Produto mais vendido")
        print("12 - Ranking de produtos")
        print("0 - Sair")

        opcao = input("Escolha uma opção: ")

        # =========================
        # CADASTRAR MATÉRIA PRIMA
        # =========================
        if opcao == "1":

            nome = input("Nome da matéria-prima: ")
            unidade = input("Unidade de medida: ")
            estoque_minimo = float(input("Estoque mínimo: "))
            preco_unitario = float(input("Preço unitário: ").replace(",", "."))

            estoque.cadastrar_materia_prima(
                nome,
                unidade,
                estoque_minimo,
                preco_unitario
            )

            util.voltar_menu()

        # =========================
        # LISTAR MATÉRIA PRIMA
        # =========================
        elif opcao == "2":

            util.limpar_tela()
            dados = estoque.listar_materia_prima()

            for item in dados:
                print(item)

            util.voltar_menu()

        # =========================
        # ENTRADA ESTOQUE
        # =========================
        elif opcao == "3":

            nome = input("Nome da matéria-prima: ")
            resultados = estoque.buscar_materia_prima_por_nome(nome)

            if not resultados:
                print("Não encontrado.")
            else:
                for item in resultados:
                    print(item)

                materia_prima_id = int(input("Escolha o ID: "))
                quantidade = float(input("Quantidade de entrada: "))

                estoque.entrada_estoque(materia_prima_id, quantidade)

            util.voltar_menu()

        # =========================
        # SAÍDA ESTOQUE
        # =========================
        elif opcao == "4":

            nome = input("Nome da matéria-prima: ")
            resultados = estoque.buscar_materia_prima_por_nome(nome)

            if not resultados:
                print("Não encontrado.")
            else:
                for item in resultados:
                    print(item)

                materia_prima_id = int(input("Escolha o ID: "))
                quantidade = float(input("Quantidade de saída: "))

                estoque.saida_estoque(materia_prima_id, quantidade)

            util.voltar_menu()

        # =========================
        # VER ESTOQUE ATUAL
        # =========================
        elif opcao == "5":

            nome = input("Nome da matéria-prima: ")
            resultados = estoque.buscar_materia_prima_por_nome(nome)

            if not resultados:
                print("Nenhum encontrado.")
            else:

                print("\nEstoque atual:\n")

                for id_mp, nome_mp, unidade in resultados:
                    estoque_atual = estoque.calcular_estoque(id_mp)
                    print(f"ID: {id_mp} | {nome_mp} | Estoque: {estoque_atual} {unidade}")

            util.voltar_menu()

        # =========================
        # VENDER PRODUTO
        # =========================
        elif opcao == "9":

            nome = input("Nome do produto: ")
            resultados = produtos.buscar_produto_por_nome(nome)

            if not resultados:
                print("Produto não encontrado.")
            else:

                print("\nProdutos encontrados:")

                for item in resultados:
                    print(item)

                id_produto = int(input("\nDigite o ID escolhido: "))
                quantidade = int(input("Quantidade: "))
                preco = float(input("Preço de venda: ").replace(",", "."))

                vendas.vender_produto(
                    id_produto,
                    quantidade,
                    preco,
                    "manual"
                )

            util.voltar_menu()

        # =========================
        # COMPRAR MATÉRIA PRIMA
        # =========================
        elif opcao == "7":

            nome = input("Nome da matéria-prima: ")
            resultados = estoque.buscar_materia_prima_por_nome(nome)

            if not resultados:
                print("Não encontrado.")
            else:

                if len(resultados) == 1:
                    id_escolhido = resultados[0][0]
                    print(f"Selecionado automaticamente: {resultados[0][1]}")
                else:
                    print("\nVários encontrados:")

                    for i, item in enumerate(resultados):
                        print(i, item)

                    escolha = int(input("\nDigite o número da lista: "))
                    id_escolhido = resultados[escolha][0]

                quantidade = float(input("Quantidade comprada: "))
                preco = float(input("Preço unitário: ").replace(",", "."))

                estoque.comprar_materia_prima(
                    id_escolhido,
                    quantidade,
                    preco
                )

            util.voltar_menu()

        # =========================
        # CADASTRAR PRODUTO
        # =========================
        elif opcao == "6":

            nome = input("Nome do produto: ")
            preco = float(input("Preço de venda: ").replace(",", "."))
            categoria = input("Categoria: ")

            id_produto = produtos.cadastrar_produto(
                nome,
                preco,
                categoria
            )

            if id_produto:
                print("\n=== MONTAR RECEITA ===")
                receitas.montar_receita(id_produto)

            util.voltar_menu()

        # =========================
        # ALERTA ESTOQUE
        # =========================
        elif opcao == "8":

            util.limpar_tela()
            estoque.verificar_alerta_estoque()
            util.voltar_menu()

        # =========================
        # RELATÓRIO
        # =========================
        elif opcao == "10":

            util.limpar_tela()
            vendas.relatorio_financeiro()
            util.voltar_menu()

        # =========================
        # PRODUTO MAIS VENDIDO
        # =========================
        elif opcao == "11":

            vendas.produto_mais_vendido()
            util.voltar_menu()

        # =========================
        # RANKING PRODUTOS
        # =========================
        elif opcao == "12":

            vendas.ranking_produtos()
            util.voltar_menu()

        # =========================
        # SAIR
        # =========================
        elif opcao == "0":

            print("Encerrando sistema...")
            break

        else:
            print("Opção inválida!")
            util.voltar_menu()