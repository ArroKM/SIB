"""
Routes package.
"""
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.surat import surat_bp
from app.routes.reports import reports_bp
from app.routes.users import users_bp
from app.routes.notifications import notifications_bp
from app.routes.api import api_bp
from app.routes.api_external import api_external_bp

__all__ = [
    'auth_bp',
    'dashboard_bp',
    'surat_bp',
    'reports_bp',
    'users_bp',
    'notifications_bp',
    'api_bp',
    'api_external_bp',
]
