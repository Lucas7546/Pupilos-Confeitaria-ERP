from dotenv import load_dotenv
from modules.usuarios import buscar_usuario

load_dotenv()

user_data = buscar_usuario("admin")

u = User(user_data)

print(u.id)
print(u.username)
print(u.nivel)
print(u.id_empresa)