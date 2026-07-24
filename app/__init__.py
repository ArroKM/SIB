"""
Flask application factory.
Creates and configures the Flask application.
"""
import os
from datetime import datetime

from flask import Flask, render_template, g

# Get the base directory (parent of app/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from app.config import Config
from app.extensions import init_extensions
from app.database import init_db, get_db


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__,
                template_folder=os.path.join(BASE_DIR, 'templates'),
                static_folder=os.path.join(BASE_DIR, 'static'))
    app.config.from_object(config_class)

    # Initialize app-specific settings FIRST
    config_class.init_app(app)

    # IMPORTANT: Import models to register user_loader decorator BEFORE init_extensions
    from app.models.user import User

    # Initialize extensions (login_manager, csrf, etc.)
    init_extensions(app)

    # Register blueprints
    from app.routes import (
        auth_bp, dashboard_bp, surat_bp, reports_bp,
        users_bp, notifications_bp, api_bp,
    )
    from app.routes.api_external import api_external_bp

    # Register all blueprints without prefix to maintain backward compatibility
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(surat_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(api_external_bp)  # External API with /api/v1 prefix

    # Cleanup database connection
    @app.teardown_appcontext
    def close_db(exc):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    # Context processor for global variables
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from app.utils.helpers import query_one

        notif_count = 0
        if current_user.is_authenticated:
            try:
                conn = get_db()
                row = query_one(conn,
                                "SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=0",
                                (current_user.id,))
                notif_count = row['c'] if row else 0
                conn.close()
            except Exception:
                pass
        return dict(
            app_name=Config.APP_NAME,
            company_name=Config.COMPANY_NAME,
            company_sub=Config.COMPANY_SUB,
            now=datetime.now(),
            notif_count=notif_count,
        )

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('error.html', code=403,
                               message='Anda tidak memiliki akses ke halaman ini.'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', code=404,
                               message='Halaman tidak ditemukan.'), 404

    return app
