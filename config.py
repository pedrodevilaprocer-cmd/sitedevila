import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', 'segredo_devila_tech_fixo_2025')
GEMINI_API_KEY = "AIzaSyCNmvcEjWb1mxnp920EYXs7b6s97Fpgxqw" # Consider moving this to env var
NUMERO_DOUTORA = "5548999195339"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BASE_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'producao')
SAFE_UPLOADS_FOLDER = os.path.join(BASE_DIR, 'safe_uploads')

# Ensure folders exist
for path in [UPLOAD_BASE_FOLDER, SAFE_UPLOADS_FOLDER]:
    if not os.path.exists(path): os.makedirs(path)

API_URL_BUSCA = "https://n8n.procer.com.br/webhook/item-m2"
API_TOKEN = "eyJhbGciOiJSUzI1NiIsImFscGhhIjo5NjUwMH0..."
SMTP_SERVER = os.getenv('SMTP_SERVER', "smtp.gmail.com")
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
MY_EMAIL = os.getenv('EMAIL_USER')
MY_PASSWORD = os.getenv('EMAIL_PASS')

WHATSAPP_API_URL = "http://localhost:8081"
WHATSAPP_API_KEY = "123456"
