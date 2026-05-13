import sqlite3
conexao = sqlite3.connect("data/confeitaria.db")

cursor = conexao.cursor()

print("Banco conectado com sucesso!")

