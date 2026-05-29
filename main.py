from dotenv import load_dotenv
load_dotenv()
import os
from menu import iniciar_menu

if __name__ == "__main__":

    # garante pasta data
    if not os.path.exists("data"):
        os.makedirs("data")

    iniciar_menu()
