import os
from flask import Flask, render_template
from flask_login import LoginManager
from app.config import Config
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions with PySQLite
    db.init_app(app)
    login_manager.init_app(app)
    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Register Blueprints
    from app.auth.routes import auth_bp
    from app.tickets.routes import tickets_bp
    from app.admin.routes import admin_bp
    from app.team_admin.routes import team_admin_bp
    from app.kb.routes import kb_bp
    from app.api.routes import api_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(team_admin_bp, url_prefix='/team')
    app.register_blueprint(kb_bp, url_prefix='/kb')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Root redirect / home route
    @app.route('/')
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif current_user.role in ['team_admin', 'supervisor'] and current_user.team_id:
                return redirect(url_for('team_admin.dashboard'))
            return redirect(url_for('tickets.list_tickets'))
        return redirect(url_for('auth.login'))
        
    # Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app
