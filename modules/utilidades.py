print("UTILIDADES CARREGADO")

import os

def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")

def voltar_menu():
    input("\nENTER para voltar ao menu...")
    limpar_tela()

def esperar():
    input("\nENTER para continuar...")

def finalizar_acao():
    input("\nPressione ENTER...")

def pausar():
    input("\nPressione ENTER para continuar...")

def tela_final():
    while True:
        opcao = input("\n[ENTER] voltar | [0] sair: ")

        if opcao == "0":
            print("Encerrando sistema...")
            exit()
        else:
            return

def voltar_ou_sair():
    while True:
        opcao = input("\n[ENTER] voltar | [0] sair: ")

        if opcao == "0":
            print("Encerrando sistema...")
            exit()
        else:
            return