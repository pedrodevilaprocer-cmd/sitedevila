import re
from datetime import datetime, timedelta
from database import get_db_connection
from services.whatsapp_service import enviar_whatsapp_api
try:
    import google.generativeai as genai
except ImportError:
    print("⚠️ AVISO CRÍTICO: 'google-generativeai' não instalado.", flush=True)
    genai = None

from config import GEMINI_API_KEY

if genai and "AIza" in GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
