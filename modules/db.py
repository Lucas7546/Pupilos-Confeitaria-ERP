import sqlite3

DB_PATH = "data/confeitaria.db"

def conectar():
    return sqlite3.connect(DB_PATH)