"""
Flask extensions initialization.
Centralizes all Flask extension instances.
"""
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Flask extensions
login_manager = LoginManager()
csrf = CSRFProtect()

# Login manager configuration
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Silakan login terlebih dahulu.'
login_manager.login_message_category = 'warning'


def init_extensions(app):
    """Initialize all extensions with the Flask app."""
    login_manager.init_app(app)
    csrf.init_app(app)
