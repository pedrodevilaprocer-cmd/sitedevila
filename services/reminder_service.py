import threading
import time
from datetime import datetime, timedelta
from database import get_db_connection
from services.whatsapp_service import enviar_whatsapp_api

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
