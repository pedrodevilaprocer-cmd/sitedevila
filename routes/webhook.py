import re
from datetime import datetime
from flask import Blueprint, request, jsonify
from services.ai_service import perguntar_ia_doutora
from services.whatsapp_service import enviar_whatsapp_api
from database import get_db_connection
from config import NUMERO_DOUTORA

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/api/webhook/whatsapp', methods=['POST'])
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
