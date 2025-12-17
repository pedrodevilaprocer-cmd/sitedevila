import os
import sqlite3
from werkzeug.security import generate_password_hash

if not os.path.exists('instance'): os.makedirs('instance')
DB_MAIN = os.path.join('instance', 'database.db')
DB_CARABELI = os.path.join('instance', 'carabeli.db')

def get_db_connection(db_name='main'):
    target = DB_CARABELI if db_name == 'carabeli' else DB_MAIN
    conn = sqlite3.connect(target)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

def init_dbs():
    try:
        with sqlite3.connect(DB_MAIN) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT, senha TEXT, empresa TEXT, cargo TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS active_projects (id TEXT PRIMARY KEY, descricao TEXT, added_by TEXT, added_at DATETIME)''')
            if not c.execute("SELECT * FROM users WHERE email='admin@devilatech.com.br'").fetchone():
                c.execute("INSERT INTO users (nome, email, senha, empresa, cargo) VALUES (?, ?, ?, ?, ?)", ('Admin', 'admin@devilatech.com.br', generate_password_hash('123'), 'admin', 'Master'))
            if not c.execute("SELECT * FROM users WHERE email='doutora@carabeli.com'").fetchone():
                c.execute("INSERT INTO users (nome, email, senha, empresa, cargo) VALUES (?, ?, ?, ?, ?)", ('Dra. Carabelli', 'doutora@carabeli.com', generate_password_hash('123'), 'carabeli', 'Dentista'))

        with sqlite3.connect(DB_CARABELI) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS pacientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, cpf TEXT, plano TEXT, telefone TEXT, email TEXT, nascimento TEXT, cep TEXT, endereco TEXT, numero TEXT, bairro TEXT, cidade TEXT, estado TEXT, anamnese TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS atendimentos_ativos (id TEXT PRIMARY KEY, nome TEXT, added_by TEXT, added_at DATETIME)''')
            c.execute('''CREATE TABLE IF NOT EXISTS financeiro (id INTEGER PRIMARY KEY AUTOINCREMENT, paciente_id INTEGER, data TEXT, servico TEXT, valor REAL, obs TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY AUTOINCREMENT, paciente_id INTEGER, paciente_nome TEXT, start_time TEXT, end_time TEXT, procedimento TEXT, status TEXT DEFAULT 'Agendado', obs TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS estoque (id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT, qtd INTEGER, unidade TEXT, validade TEXT, status TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS whatsapp_config (id INTEGER PRIMARY KEY CHECK (id = 1), hora_envio TEXT DEFAULT '09:00', status TEXT DEFAULT 'ativo')''')
            c.execute("INSERT OR IGNORE INTO whatsapp_config (id, hora_envio, status) VALUES (1, '09:00', 'ativo')")

        print("✅ Bancos de Dados Sincronizados!", flush=True)
    except Exception as e: print(f"Erro DB: {e}", flush=True)
