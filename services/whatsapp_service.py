import re
import requests
from config import WHATSAPP_API_URL, WHATSAPP_API_KEY

def enviar_whatsapp_api(telefone, mensagem):
    telefone = re.sub(r'\D', '', str(telefone))
    if not telefone: return
    if not telefone.startswith('55') and len(telefone) >= 10: telefone = '55' + telefone
    url = f"{WHATSAPP_API_URL}/message/sendText/clinica_carabelli"
    payload = {"number": telefone, "options": {"delay": 1200, "presence": "composing"}, "textMessage": {"text": mensagem}}
    headers = {"apikey": WHATSAPP_API_KEY, "Content-Type": "application/json"}
    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"❌ Erro Zap: {e}", flush=True)
