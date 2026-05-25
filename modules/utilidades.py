import os
import sys
from utils.logger import log_info # Importando para registrar encerramentos

def limpar_tela():
    """Limpa o console de acordo com o sistema operacional."""
    os.system("cls" if os.name == "nt" else "clear")

def pausar():
    """Apenas uma pausa simples antes de seguir o fluxo."""
    input("\nPressione ENTER para continuar...")

def voltar_menu():
    """Pausa e limpa a tela para retornar ao menu principal."""
    input("\nENTER para voltar ao menu...")
    limpar_tela()

def tela_final():
    """Oferece a opção de retornar ou encerrar o programa."""
    while True:
        opcao = input("\n[ENTER] Voltar ao Menu | [0] Sair do Sistema: ").strip()

        if opcao == "0":
            log_info("Sistema encerrado pelo usuário.") # Registro do encerramento
            print("\nEncerrando sistema Pupilos Confeitaria... Até logo!")
            sys.exit()
        else:
            limpar_tela()
            return

def voltar_ou_sair():
    """Alias para tela_final."""
    return tela_final()