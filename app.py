import os
import threading
import warnings
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from config import SECRET_KEY
from database import init_dbs
from routes import register_routes
from services.reminder_service import verificar_lembretes_automaticos

warnings.filterwarnings("ignore")

# Define paths explicitly to avoid issues on Windows/different CWD
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = SECRET_KEY

# Register Blueprints
register_routes(app)

if __name__ == '__main__':
    init_dbs()
    threading.Thread(target=verificar_lembretes_automaticos, daemon=True).start()
    from waitress import serve
    print("🚀 Servidor Devila Tech (MESTRE FULL) Rodando na porta 8000...", flush=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    serve(app, host='0.0.0.0', port=8000, threads=8)
