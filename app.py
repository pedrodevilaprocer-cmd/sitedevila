import os
import re
import json
import mimetypes
import smtplib
import sqlite3
import requests
import threading
import time
import base64
from datetime import timedelta, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix 
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

import warnings
warnings.filterwarnings("ignore") 

try:
    import google.generativeai as genai
except ImportError:
    print("⚠️ AVISO CRÍTICO: 'google-generativeai' não instalado.", flush=True)
    genai = None

# ==========================================
# 1. CONFIGURAÇÕES GERAIS
# ==========================================
load_dotenv()

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.getenv('SECRET_KEY', 'segredo_devila_tech_fixo_2025')
app.permanent_session_lifetime = timedelta(days=30)

# --- [SUA CHAVE AQUI] ---
GEMINI_API_KEY = "AIzaSyCNmvcEjWb1mxnp920EYXs7b6s97Fpgxqw"  # <--- CERTIFIQUE-SE DE QUE SUA CHAVE ESTÁ AQUI

if genai and "AIza" in GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- SEU NÚMERO PESSOAL ---
NUMERO_DOUTORA = "5548999195339" 

# --- Configuração de Pastas ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BASE_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'producao')
SAFE_UPLOADS_FOLDER = os.path.join(BASE_DIR, 'safe_uploads')

for path in [UPLOAD_BASE_FOLDER, SAFE_UPLOADS_FOLDER]:
    if not os.path.exists(path): os.makedirs(path)

# --- APIs e Email ---
API_URL_BUSCA = "https://n8n.procer.com.br/webhook/item-m2"
API_TOKEN = "eyJhbGciOiJSUzI1NiIsImFscGhhIjo5NjUwMH0..." 
SMTP_SERVER = os.getenv('SMTP_SERVER', "smtp.gmail.com")
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
MY_EMAIL = os.getenv('EMAIL_USER')
MY_PASSWORD = os.getenv('EMAIL_PASS')

# ==========================================
# 2. BANCOS DE DADOS
# ==========================================
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

# ==========================================
# 3. UTILITÁRIOS GERAIS
# ==========================================
def limpar_nome(nome): return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', str(nome)).strip()

def get_target_folder(company, folder_id):
    company_path = os.path.join(SAFE_UPLOADS_FOLDER, company)
    if not os.path.exists(company_path): os.makedirs(company_path)
    prefix_type = "projeto" if company == 'procer' else "paciente"
    base_prefix = f"{prefix_type}_{folder_id}"
    for folder_name in os.listdir(company_path):
        if folder_name.startswith(base_prefix + "_") or folder_name == base_prefix:
            return os.path.join(company_path, folder_name), folder_name
    item_name = "Item"
    try:
        conn = get_db_connection('carabeli' if company=='carabeli' else 'main')
        sql = "SELECT nome FROM pacientes WHERE id=?" if company=='carabeli' else "SELECT descricao FROM active_projects WHERE id=?"
        res = conn.execute(sql, (folder_id,)).fetchone()
        if res: item_name = res[0]
        conn.close()
    except: pass
    new_folder_name = f"{base_prefix}_{limpar_nome(item_name)}"
    full_path = os.path.join(company_path, new_folder_name)
    os.makedirs(full_path, exist_ok=True)
    return full_path, new_folder_name

def get_metadata_path(full_path): return os.path.join(full_path, '_metadata.json')
def load_metadata(full_path):
    path = get_metadata_path(full_path)
    if os.path.exists(path):
        try: return json.load(open(path, 'r'))
        except: return {}
    return {}
def save_metadata(full_path, data):
    with open(get_metadata_path(full_path), 'w') as f: json.dump(data, f)

def enviar_whatsapp_api(telefone, mensagem):
    telefone = re.sub(r'\D', '', str(telefone)) 
    if not telefone: return
    if not telefone.startswith('55') and len(telefone) >= 10: telefone = '55' + telefone
    url = "http://localhost:8081/message/sendText/clinica_carabelli"
    payload = {"number": telefone, "options": {"delay": 1200, "presence": "composing"}, "textMessage": {"text": mensagem}}
    headers = {"apikey": "123456", "Content-Type": "application/json"}
    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"❌ Erro Zap: {e}", flush=True)

# ==========================================
# 4. INTELIGÊNCIA ARTIFICIAL & FERRAMENTAS REAIS
# ==========================================

def processar_comandos_reais(mensagem_doutora):
    """
    Interpreta comandos da Doutora e executa no Banco de Dados.
    """
    msg_lower = mensagem_doutora.lower()
    
    # --- FERRAMENTA 1: CANCELAR ---
    if "cancelar" in msg_lower or "retira da agenda" in msg_lower or "remove" in msg_lower:
        print("🔧 [FERRAMENTA] Cancelamento acionado...", flush=True)
        try:
            conn = get_db_connection('carabeli')
            hoje = datetime.now().strftime('%Y-%m-%d')
            agendas = conn.execute("SELECT * FROM agenda WHERE start_time >= ? AND status != 'Concluído'", (hoje,)).fetchall()
            paciente_alvo = None
            for ag in agendas:
                if ag['paciente_nome'].lower() in msg_lower or ag['paciente_nome'].split()[0].lower() in msg_lower:
                    paciente_alvo = ag; break
            if paciente_alvo:
                conn.execute("DELETE FROM agenda WHERE id = ?", (paciente_alvo['id'],)); conn.commit()
                aviso = f"Agendamento de {paciente_alvo['paciente_nome']} excluído."
                pac = conn.execute("SELECT telefone FROM pacientes WHERE id=?", (paciente_alvo['paciente_id'],)).fetchone()
                if pac and pac['telefone']:
                    enviar_whatsapp_api(pac['telefone'], "Olá! Sua consulta precisou ser cancelada. Entraremos em contato."); aviso += " Paciente avisado."
                conn.close(); return f"SUCESSO: {aviso}"
            conn.close(); return "ERRO: Não achei esse nome na agenda futura."
        except Exception as e: return f"ERRO: {e}"

    # --- FERRAMENTA 2: AGENDAR (CRIAR NO BANCO) ---
    # Gatilho: "agendar [nome] as [horas]"
    if "agendar" in msg_lower and ":" in msg_lower:
        print("🔧 [FERRAMENTA] Criação de Agenda acionada...", flush=True)
        try:
            conn = get_db_connection('carabeli')
            pacientes = conn.execute("SELECT id, nome FROM pacientes").fetchall()
            
            # 1. Acha o paciente
            found_pac = None
            for p in pacientes:
                if p['nome'].lower() in msg_lower or p['nome'].split()[0].lower() in msg_lower: found_pac = p; break
            
            # 2. Acha o horário (Regex simples para HH:MM)
            match_hora = re.search(r'(\d{1,2}:\d{2})', msg_lower)
            
            if found_pac and match_hora:
                hora = match_hora.group(1)
                # Formata a data (assume amanhã, a menos que diga 'hoje')
                hoje_dt = datetime.now()
                dia_alvo = hoje_dt if 'hoje' in msg_lower else (hoje_dt + timedelta(days=1))
                
                # Se for "segunda", "terça" (logica complexa), por enquanto simplificamos para Amanhã/Hoje
                # Ajusta o horário na data
                h, m = map(int, hora.split(':'))
                data_final = dia_alvo.replace(hour=h, minute=m, second=0).strftime('%Y-%m-%dT%H:%M')
                
                # Insere no Banco
                conn.execute("INSERT INTO agenda (paciente_id, paciente_nome, start_time, end_time, procedimento, status) VALUES (?,?,?,?,?,?)",
                             (found_pac['id'], found_pac['nome'], data_final, data_final, 'Consulta', 'Agendado'))
                conn.commit()
                conn.close()
                return f"SUCESSO: Agendei {found_pac['nome']} para {dia_alvo.strftime('%d/%m')} às {hora}."
            
            conn.close()
            if not found_pac: return "ERRO: Não achei o paciente no banco."
            if not match_hora: return "ERRO: Não entendi o horário (use formato HH:MM)."
        except Exception as e: return f"ERRO AO AGENDAR: {e}"

    # --- FERRAMENTA 3: MANDAR MENSAGEM (AVISAR/PERGUNTAR) ---
    gatilhos_msg = ["mande mensagem", "avisar", "pergunte", "fale com", "chama o", "agendando para"]
    if any(g in msg_lower for g in gatilhos_msg):
        print("🔧 [FERRAMENTA] Envio Mensagem acionado...", flush=True)
        conn = get_db_connection('carabeli')
        pacientes = conn.execute("SELECT nome, telefone FROM pacientes").fetchall()
        conn.close()
        
        found = None
        for p in pacientes:
            if p['nome'].lower() in msg_lower or p['nome'].split()[0].lower() in msg_lower: found = p; break
        
        if found:
            if not found['telefone']: return f"ERRO: {found['nome']} não tem telefone."
            
            # IA escreve a mensagem para o paciente
            texto_zap = f"Olá {found['nome']}! A Dra. Carabelli pediu para entrar em contato."
            try:
                # Usa um modelo leve para gerar o texto do zap
                modelos = ["gemini-1.5-flash", "gemini-2.0-flash-lite-preview-02-05"]
                for m_nome in modelos:
                    try:
                        modelo_rapido = genai.GenerativeModel(m_nome)
                        prompt_msg = f"A Dra. Carabelli pediu: '{mensagem_doutora}'. Escreva apenas a mensagem de WhatsApp para enviar ao paciente {found['nome']}. Seja curta e educada."
                        texto_zap = modelo_rapido.generate_content(prompt_msg).text
                        break
                    except: continue
            except: pass

            enviar_whatsapp_api(found['telefone'], texto_zap)
            return f"SUCESSO: Enviei para {found['nome']}: '{texto_zap}'"
        
        return "ERRO: Não encontrei paciente com esse nome."

    return None

def get_dados_clinica_contexto():
    try:
        conn = get_db_connection('carabeli')
        hoje = datetime.now().strftime('%Y-%m-%d')
        agenda = conn.execute("SELECT start_time, paciente_nome, procedimento, status FROM agenda WHERE start_time >= ? ORDER BY start_time ASC LIMIT 10", (hoje,)).fetchall()
        faturamento = conn.execute("SELECT SUM(valor) as total FROM financeiro WHERE data = ?", (hoje,)).fetchone()
        total_fat = faturamento['total'] or 0.0
        conn.close()
        
        txt_agenda = ""
        if not agenda: txt_agenda = "Sem agendamentos futuros."
        else:
            for item in agenda:
                dt = datetime.fromisoformat(item['start_time']).strftime('%d/%m às %H:%M')
                txt_agenda += f"- {dt}: {item['paciente_nome']} ({item['procedimento']}) [{item['status']}]\n"
        
        return f"RESUMO:\nFaturamento Hoje: R$ {total_fat:.2f}\n\nAGENDA:\n{txt_agenda}"
    except: return "Erro dados."

# --- CÉREBRO GEMINI (RODÍZIO) ---
def perguntar_ia_doutora(pergunta):
    if not genai or "AIza" not in GEMINI_API_KEY: return "⚠️ Configure a API Key."
    
    # 1. Ferramentas (Prioridade)
    acao = processar_comandos_reais(pergunta)
    if acao: return f"🤖 [AÇÃO]: {acao}"

    # 2. IA com Fallback
    dados = get_dados_clinica_contexto()
    
    modelos_disponiveis = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-2.0-flash-lite-preview-02-05", 
        "gemini-1.0-pro"
    ]
    
    for modelo_nome in modelos_disponiveis:
        try:
            model = genai.GenerativeModel(modelo_nome)
            prompt = f"Você é a secretária da Dra. Carabelli. Dados:\n{dados}\nPergunta: {pergunta}\nResponda curto."
            resp = model.generate_content(prompt)
            return resp.text
        except Exception as e:
            if "429" in str(e):
                print(f"⏳ Cota ({modelo_nome}) cheia. Trocando...", flush=True)
                continue
            if "404" in str(e): continue
    
    return "IA sobrecarregada (Google Free Tier). Aguarde 30s."

# ==========================================
# 5. ROBÔ & WEBHOOK
# ==========================================
def verificar_lembretes_automaticos():
    print("🤖 Robô de Lembretes Ativo...", flush=True)
    ultima_assinatura = None
    while True:
        try:
            time.sleep(5)
            try:
                conn = get_db_connection('carabeli')
                cfg = conn.execute("SELECT * FROM whatsapp_config WHERE id=1").fetchone()
                conn.close()
            except: continue
            
            if not cfg or cfg['status'] != 'ativo': continue
            
            hora_conf = cfg['hora_envio']
            agora = datetime.now()
            assinatura = f"{agora.strftime('%Y-%m-%d')}|{hora_conf}"
            if ultima_assinatura == assinatura: continue
            
            h, m = map(int, hora_conf.split(':'))
            min_agora = agora.hour * 60 + agora.minute
            min_alvo = h * 60 + m
            
            if 0 <= (min_agora - min_alvo) < 3:
                print(f"⏰ Hora dos Lembretes ({hora_conf})!", flush=True)
                amanha = (agora + timedelta(days=1)).strftime('%Y-%m-%d')
                dt_fmt = (agora + timedelta(days=1)).strftime('%d/%m')
                conn = get_db_connection('carabeli')
                agendas = conn.execute("SELECT a.*, p.telefone, p.nome FROM agenda a JOIN pacientes p ON a.paciente_id = p.id WHERE a.start_time LIKE ? AND a.status != 'Concluído'", (f'{amanha}%',)).fetchall()
                conn.close()
                for ag in agendas:
                    if ag['telefone']:
                        msg = f"Olá {ag['nome'].split()[0]}! 🦷\nLembrete de consulta amanhã ({dt_fmt}) às {ag['start_time'].split('T')[1][:5]}.\nResponda SIM para confirmar."
                        enviar_whatsapp_api(ag['telefone'], msg)
                        time.sleep(5)
                ultima_assinatura = assinatura
        except: time.sleep(10)

@app.route('/api/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    try:
        data = request.json.get('data', {})
        msg_info = data.get('message', {})
        key = data.get('key', {})
        texto = msg_info.get('conversation') or msg_info.get('extendedTextMessage', {}).get('text') or ""
        
        candidatos = []
        if key.get('remoteJid'): candidatos.append(key.get('remoteJid').split('@')[0])
        if key.get('participant'): candidatos.append(key.get('participant').split('@')[0])
        candidatos = list(set(filter(None, candidatos)))
        
        if not texto or not candidatos: return jsonify({'status':'ignored'}), 200
        
        print(f"📨 Msg: '{texto}' | De: {candidatos}", flush=True)

        # 1. É A DOUTORA?
        doc_clean = re.sub(r'\D', '', NUMERO_DOUTORA)[-8:] 
        eh_doutora = False
        tel_doutora = ""
        for c in candidatos:
            if c[-8:] == doc_clean: eh_doutora = True; tel_doutora = c; break
        
        if eh_doutora:
            print(f"   🤖 Doutora detectada! Processando...", flush=True)
            resp = perguntar_ia_doutora(texto)
            enviar_whatsapp_api(tel_doutora, resp)
            return jsonify({'status':'ai_replied'}), 200

        # 2. É PACIENTE?
        # A) Confirmação Simples
        if any(p in texto.lower() for p in ['sim', 'ok', 'confirmo', 'confirmado', '👍']):
            print("   ✅ Confirmação detectada!", flush=True)
            conn = get_db_connection('carabeli')
            pacientes = conn.execute("SELECT id, nome, telefone FROM pacientes WHERE telefone IS NOT NULL").fetchall()
            found = None
            for c in candidatos:
                c_final = c[-8:]
                for p in pacientes:
                    if re.sub(r'\D','',str(p['telefone']))[-8:] == c_final: found = p; break
                if found: break
            
            if found:
                hoje = datetime.now().strftime('%Y-%m-%d')
                res = conn.execute("UPDATE agenda SET status='Confirmado' WHERE paciente_id=? AND status='Agendado' AND start_time >= ?", (found['id'], hoje))
                conn.commit()
                if res.rowcount > 0:
                    enviar_whatsapp_api(candidatos[0], "Confirmado! ✅ Nos vemos lá.")
                    print("   🎉 Agenda atualizada!", flush=True)
            conn.close()
        
        # B) Resposta Diferente (Encaminha para Doutora)
        else:
            # Se não for a doutora e não for confirmação, encaminha
            print("   📩 Resposta do paciente! Encaminhando para Dra...", flush=True)
            
            # Tenta identificar o nome
            conn = get_db_connection('carabeli')
            pacientes = conn.execute("SELECT nome, telefone FROM pacientes WHERE telefone IS NOT NULL").fetchall()
            conn.close()
            
            nome_remetente = "Paciente Desconhecido"
            for c in candidatos:
                c_final = c[-8:]
                for p in pacientes:
                    if re.sub(r'\D','',str(p['telefone']))[-8:] == c_final: 
                        nome_remetente = p['nome']
                        break
            
            # Manda para o seu WhatsApp pessoal
            aviso = f"📩 *Nova Mensagem de {nome_remetente}*:\n\n{texto}"
            enviar_whatsapp_api(NUMERO_DOUTORA, aviso)

        return jsonify({'status':'processed'}), 200
    except Exception as e:
        print(f"❌ Erro Webhook: {e}", flush=True)
        return jsonify({'error':str(e)}), 500

# ==========================================
# 7. ROTAS WEB (TODAS AS EMPRESAS)
# ==========================================
@app.route('/')
def home(): return render_template('index.html')

@app.route('/login', methods=['GET','POST'])
def login(): 
    if request.method=='POST':
        email=request.form.get('email'); senha=request.form.get('senha')
        conn=get_db_connection('main'); user=conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); conn.close()
        if user and check_password_hash(user['senha'], senha):
            session['user_id']=user['id']; session['nome']=user['nome']; session['empresa']=user['empresa']
            return redirect('/admin' if user['empresa']=='admin' else f"/cliente/{user['empresa']}")
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('empresa') != 'admin': return redirect('/login')
    conn = get_db_connection('main')
    if request.method == 'POST':
        conn.execute('UPDATE users SET empresa=?, cargo=? WHERE id=?', (request.form.get('nova_empresa'), request.form.get('novo_cargo'), request.form.get('user_id'))); conn.commit()
        flash("Atualizado.")
    users = conn.execute('SELECT * FROM users').fetchall(); conn.close()
    return render_template('admin.html', users=users)

@app.route('/admin/excluir', methods=['POST'])
def excluir():
    conn = get_db_connection('main'); conn.execute('DELETE FROM users WHERE id=?', (request.form.get('user_id'),)); conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/cliente/procer')
def rota_procer(): return render_template('clientes/procer_dashboard.html') if session.get('empresa')=='procer' else redirect('/login')

@app.route('/cliente/procer/testes')
def procer_testes_dashboard(): return render_template('clientes/dashboard_testes.html', user_name=session['nome']) if session.get('empresa')=='procer' else redirect('/login')

@app.route('/cliente/procer/testes/lista')
def procer_testes_lista(): return render_template('clientes/procer_testes.html', ops=[]) if session.get('empresa')=='procer' else redirect('/login')

@app.route('/api/projetos-quadros')
def api_projetos_quadros():
    termo = request.args.get('q', '')
    try:
        h = {'Content-Type': 'application/json', 'Authorization': API_TOKEN}
        r = requests.get(API_URL_BUSCA, headers=h, params={"filter": termo}, timeout=10)
        return jsonify(r.json()[:100] if r.status_code == 200 else [])
    except: return jsonify([])

@app.route('/api/active_projects', methods=['GET', 'POST', 'DELETE'])
def manage_active_projects():
    conn = get_db_connection('main')
    if request.method == 'GET': r = conn.execute('SELECT * FROM active_projects ORDER BY added_at DESC').fetchall(); conn.close(); return jsonify([dict(x) for x in r])
    if request.method == 'POST': d = request.json; conn.execute('INSERT OR IGNORE INTO active_projects (id, descricao, added_by, added_at) VALUES (?, ?, ?, ?)', (d['id'], d['descricao'], session['nome'], datetime.now())); conn.commit(); conn.close(); return jsonify({'success': True})
    if request.method == 'DELETE': conn.execute('DELETE FROM active_projects WHERE id = ?', (request.args.get('id'),)); conn.commit(); conn.close(); return jsonify({'success': True})

@app.route('/upload_evidencias', methods=['POST'])
def upload_evidencias():
    try:
        path = os.path.join(UPLOAD_BASE_FOLDER, limpar_nome(request.form.get('item_desc')), limpar_nome(f"OV_{request.form.get('ov_numero')}"))
        if not os.path.exists(path): os.makedirs(path)
        for i in range(4):
            if f'foto_{i}' in request.files: f = request.files[f'foto_{i}']; f.save(os.path.join(path, f"OP_{request.form.get('op_numero')}_{i}.jpg"))
        return jsonify({'success': True})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/cliente/carabeli')
def rota_carabeli(): return render_template('clientes/carabeli_dashboard.html', user_name=session.get('nome','Doutora')) if session.get('empresa')=='carabeli' else redirect('/login')

@app.route('/api/clinica/whatsapp/config', methods=['GET','POST'])
def api_wa_cfg():
    conn=get_db_connection('carabeli')
    if request.method=='GET': r=conn.execute("SELECT * FROM whatsapp_config").fetchone(); conn.close(); return jsonify(dict(r))
    d=request.json; conn.execute("UPDATE whatsapp_config SET hora_envio=?, status=?",(d['hora_envio'],d['status'])); conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/clinica/whatsapp/connect')
def api_wa_conn():
    try:
        h={"apikey":"123456","Content-Type":"application/json"}
        r=requests.post("http://localhost:8081/instance/create",json={"instanceName":"clinica_carabelli","qrcode":True},headers=h).json()
        if "already exists" in str(r): r=requests.get("http://localhost:8081/instance/connect/clinica_carabelli",headers=h).json()
        if r.get('instance',{}).get('state')=='open': return jsonify({'status':'connected'})
        qr = r.get('qrcode',{}).get('base64') or r.get('base64')
        if qr: return jsonify({'status':'qrcode','qrcode':qr.replace("data:image/png;base64,","").strip()})
        return jsonify({'status':'unknown'})
    except: return jsonify({'error':'erro'})

@app.route('/api/clinica/whatsapp/logout', methods=['DELETE'])
def api_wa_logout(): requests.delete("http://localhost:8081/instance/logout/clinica_carabelli",headers={"apikey":"123456"}); return jsonify({'success':True})

@app.route('/api/clinica/pacientes')
def api_pacientes():
    t=request.args.get('q','').lower(); conn=get_db_connection('carabeli')
    sql="SELECT * FROM pacientes WHERE lower(nome) LIKE ? OR cpf LIKE ?" if t else "SELECT * FROM pacientes ORDER BY nome LIMIT 100"
    p=conn.execute(sql,(f'%{t}%',f'%{t}%') if t else ()).fetchall(); conn.close()
    return jsonify([{'id':str(x['id']),'nome':x['nome'],'cpf':x['cpf'],'plano':x['plano'],'telefone':x['telefone']} for x in p])

@app.route('/api/clinica/paciente/novo', methods=['POST'])
def api_pac_novo():
    d=request.json; conn=get_db_connection('carabeli')
    conn.execute("INSERT INTO pacientes (nome, cpf, plano, telefone, email, nascimento, cep, endereco, anamnese) VALUES (?,?,?,?,?,?,?,?,?)",(d['nome'],d['cpf'],d['plano'],d['telefone'],d.get('email'),d['nascimento'],d['cep'],d['endereco'],d['anamnese'])); conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/clinica/paciente/<id>', methods=['GET','PUT','DELETE'])
def api_pac_id(id):
    conn=get_db_connection('carabeli')
    if request.method=='GET': r=conn.execute("SELECT * FROM pacientes WHERE id=?",(id,)).fetchone(); conn.close(); return jsonify(dict(r) if r else {})
    if request.method=='DELETE': conn.execute("DELETE FROM pacientes WHERE id=?",(id,)); conn.commit(); conn.close(); return jsonify({'success':True})
    d=request.json; conn.execute("UPDATE pacientes SET nome=?, cpf=?, plano=?, telefone=?, nascimento=?, cep=?, endereco=?, anamnese=? WHERE id=?",(d['nome'],d['cpf'],d['plano'],d['telefone'],d['nascimento'],d['cep'],d['endereco'],d['anamnese'],id)); conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/clinica/agenda', methods=['GET','POST','PUT','DELETE'])
def api_agenda():
    conn=get_db_connection('carabeli')
    if request.method=='GET': evs=conn.execute("SELECT * FROM agenda").fetchall(); conn.close(); return jsonify([{'id':e['id'],'paciente_id':e['paciente_id'],'title':f"{e['paciente_nome']} - {e['procedimento']}",'start':e['start_time'],'end':e['end_time'],'status':e['status'],'color':'#4ade80' if e['status']=='Confirmado' else ('#94a3b8' if e['status']=='Concluído' else '#38bdf8')} for e in evs])
    d=request.json
    if request.method=='POST': conn.execute("INSERT INTO agenda (paciente_id, paciente_nome, start_time, end_time, procedimento) VALUES (?,?,?,?,?)",(d['paciente_id'],d['paciente_nome'],d['start'],d['end'],d['procedimento'])); conn.commit()
    if request.method=='PUT': conn.execute("UPDATE agenda SET status=? WHERE id=?",(d.get('status'),d.get('id'))); conn.commit()
    if request.method=='DELETE': conn.execute("DELETE FROM agenda WHERE id=?",(request.args.get('id'),)); conn.commit()
    conn.close(); return jsonify({'success':True})

@app.route('/api/clinica/financeiro/<pid>', methods=['GET','POST'])
def api_fin(pid):
    conn=get_db_connection('carabeli')
    if request.method=='POST': d=request.json; conn.execute("INSERT INTO financeiro (paciente_id, data, servico, valor) VALUES (?,?,?,?)",(pid,d['data'],d['servico'],d['valor'])); conn.commit()
    hist=conn.execute("SELECT * FROM financeiro WHERE paciente_id=? ORDER BY id DESC",(pid,)).fetchall()
    pac=conn.execute("SELECT nome FROM pacientes WHERE id=?",(pid,)).fetchone()
    conn.close(); return jsonify({'paciente':dict(pac) if pac else {},'historico':[dict(x) for x in hist]})

@app.route('/api/clinica/faturamento_hoje')
def api_fat_hoje():
    conn=get_db_connection('carabeli'); val=conn.execute("SELECT SUM(valor) FROM financeiro WHERE data=?",(datetime.now().strftime('%Y-%m-%d'),)).fetchone()[0]
    conn.close(); return jsonify({'total':val or 0.0})

@app.route('/api/clinica/relatorios')
def api_rel():
    conn=get_db_connection('carabeli')
    fin=conn.execute("SELECT f.*, p.nome as paciente_nome FROM financeiro f LEFT JOIN pacientes p ON f.paciente_id=p.id ORDER BY f.data DESC").fetchall()
    agd=conn.execute("SELECT * FROM agenda WHERE status='Concluído'").fetchall()
    conn.close(); return jsonify({'financeiro':[dict(x) for x in fin],'agenda':[dict(x) for x in agd]})

@app.route('/api/clinica/estoque', methods=['GET','POST','DELETE'])
def api_est():
    conn=get_db_connection('carabeli')
    if request.method=='GET': i=conn.execute("SELECT * FROM estoque ORDER BY item").fetchall(); conn.close(); return jsonify([dict(x) for x in i])
    if request.method=='DELETE': conn.execute("DELETE FROM estoque WHERE id=?",(request.args.get('id'),)); conn.commit()
    if request.method=='POST': d=request.json; conn.execute("INSERT INTO estoque (item, qtd, unidade, validade) VALUES (?,?,?,?)",(d['item'],d['qtd'],d['unidade'],d['validade'])); conn.commit()
    conn.close(); return jsonify({'success':True})

@app.route('/api/anexos/<target_id>', methods=['GET','POST','DELETE'])
def api_anexos(target_id):
    if 'user_id' not in session: return jsonify({'error':'401'}), 401
    emp=session.get('empresa','carabeli'); full_path,_=get_target_folder(emp, target_id)
    if request.method=='POST': f=request.files['file']; f.save(os.path.join(full_path, secure_filename(f.filename))); return jsonify({'success':True})
    if request.method=='DELETE': os.remove(os.path.join(full_path, request.json['filename'])); return jsonify({'success':True})
    return jsonify({'items':[{'name':f,'url':f"/arquivo_seguro/{emp}/{os.path.basename(full_path)}/{f}",'is_dir':False,'can_delete':True} for f in os.listdir(full_path) if f!='_metadata.json']})

@app.route('/arquivo_seguro/<company>/<folder>/<filename>')
def serve_file(company, folder, filename): return send_from_directory(os.path.join(SAFE_UPLOADS_FOLDER, company, folder), filename)

@app.route('/preencher_ficha/<int:pid>', methods=['GET','POST'])
def public_ficha(pid):
    conn=get_db_connection('carabeli')
    if request.method=='POST': conn.execute("UPDATE pacientes SET anamnese=? WHERE id=?",(request.form.get('anamnese_completa'),pid)); conn.commit(); conn.close(); return render_template('anamnese_paciente.html', sucesso=True)
    p=conn.execute("SELECT nome FROM pacientes WHERE id=?",(pid,)).fetchone(); conn.close()
    return render_template('anamnese_paciente.html', paciente_id=pid, nome_paciente=p['nome'] if p else 'Paciente')
# ==========================================
# 8. API EXCLUSIVA PARA O AGENTE N8N (IA)
# ==========================================

@app.route('/api/n8n/consultar_agenda', methods=['GET'])
def n8n_consultar_agenda():
    """
    Uso no n8n: GET http://host.docker.internal:8000/api/n8n/consultar_agenda?data=2025-12-16
    Se não enviar data, pega a de hoje.
    """
    data_alvo = request.args.get('data', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        conn = get_db_connection('carabeli')
        # Busca agendamentos que começam com a data YYYY-MM-DD
        agendamentos = conn.execute(
            "SELECT start_time, paciente_nome, procedimento, status, obs FROM agenda WHERE start_time LIKE ? ORDER BY start_time ASC",
            (f"{data_alvo}%",)
        ).fetchall()
        conn.close()

        if not agendamentos:
            return jsonify({"mensagem": f"Nenhum agendamento encontrado para {data_alvo}.", "total": 0})

        # Formata para a IA entender fácil
        lista_limpa = []
        for ag in agendamentos:
            hora = ag['start_time'].split('T')[1][:5] # Pega só HH:MM
            lista_limpa.append({
                "horario": hora,
                "paciente": ag['paciente_nome'],
                "procedimento": ag['procedimento'],
                "status": ag['status'],
                "obs": ag['obs'] or ""
            })

        return jsonify({"data": data_alvo, "agendamentos": lista_limpa, "total": len(lista_limpa)})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/n8n/buscar_paciente', methods=['GET'])
def n8n_buscar_paciente():
    """
    Uso no n8n: GET http://host.docker.internal:8000/api/n8n/buscar_paciente?nome=Joao
    """
    termo = request.args.get('nome', '').lower()
    if not termo:
        return jsonify({"erro": "Forneça um nome para busca."})

    try:
        conn = get_db_connection('carabeli')
        pacientes = conn.execute(
            "SELECT id, nome, telefone, plano, anamnese FROM pacientes WHERE lower(nome) LIKE ? LIMIT 5",
            (f"%{termo}%",)
        ).fetchall()
        conn.close()

        resultado = [dict(p) for p in pacientes]
        return jsonify(resultado)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    init_dbs()
    threading.Thread(target=verificar_lembretes_automaticos, daemon=True).start()
    from waitress import serve
    print("🚀 Servidor Devila Tech (MESTRE FULL) Rodando na porta 8000...", flush=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    serve(app, host='0.0.0.0', port=8000, threads=8)