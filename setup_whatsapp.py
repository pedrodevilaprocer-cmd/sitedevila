import requests
import base64
import time

# --- CONFIGURAÇÕES ---
API_URL = "http://localhost:8081"
API_KEY = "123456"  # <--- CONFIRA SE ESTÁ 123456
INSTANCE_NAME = "clinica_carabelli"

headers = {
    "apikey": API_KEY,
    "Content-Type": "application/json"
}

def configurar():
    print(f"🕵️  DEBUG: Tentando conectar em {API_URL}")
    print(f"🔑 DEBUG: Usando a senha: '{API_KEY}'")
    print("-" * 30)
    print(f"🔨 Criando instância '{INSTANCE_NAME}'...")
    
    url_create = f"{API_URL}/instance/create"
    payload = {
        "instanceName": INSTANCE_NAME,
        "qrcode": True
    }
    
    try:
        # Tenta criar
        response = requests.post(url_create, json=payload, headers=headers)
        
        # --- DIAGNÓSTICO DE ERROS ---
        if response.status_code == 401:
            print("\n❌ ERRO FATAL (401): Senha Recusada!")
            print("Isso significa que o Script mandou '123456', mas o Docker esperava outra coisa.")
            return

        data = response.json()

        # Sucesso na criação
        if response.status_code == 201 or (response.status_code == 200 and 'qrcode' in data):
            print("✅ Instância criada com sucesso!")
            salvar_qr(data)
            return

        # Já existe
        if "already exists" in str(data) or response.status_code == 403:
            print("⚠️ A instância já existe no servidor.")
            connect_existing()
            return
            
        print(f"❌ Resposta estranha do servidor: {response.text}")

    except Exception as e:
        print(f"❌ Erro de conexão (O Docker caiu?): {e}")

def connect_existing():
    print("🔄 Buscando QR Code de instância existente...")
    url_connect = f"{API_URL}/instance/connect/{INSTANCE_NAME}"
    resp = requests.get(url_connect, headers=headers)
    
    if resp.status_code == 200:
        salvar_qr(resp.json())
    elif resp.status_code == 401:
        print("❌ ERRO 401 ao conectar: Senha incorreta.")
    else:
        print(f"❌ Erro ao conectar: {resp.text}")

def salvar_qr(data):
    base64_code = None
    if 'qrcode' in data and data['qrcode'] and 'base64' in data['qrcode']:
        base64_code = data['qrcode']['base64']
    elif 'base64' in data:
        base64_code = data['base64']
        
    if base64_code:
        img_data = base64.b64decode(base64_code.replace('data:image/png;base64,', ''))
        with open("qrcode_whatsapp.png", "wb") as f:
            f.write(img_data)
        print("\n✨ SUCESSO! QR Code gerado em 'qrcode_whatsapp.png'")
        print("📱 Escaneie agora!")
    else:
        print("\n✅ O WhatsApp já está CONECTADO! Pode testar o envio.")

if __name__ == "__main__":
    configurar()