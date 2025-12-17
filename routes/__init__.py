from .auth import auth_bp
from .admin import admin_bp
from .procer import procer_bp
from .carabeli import carabeli_bp
from .webhook import webhook_bp
from .n8n import n8n_bp
from .main import main_bp

def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(procer_bp)
    app.register_blueprint(carabeli_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(n8n_bp)
    app.register_blueprint(main_bp)
