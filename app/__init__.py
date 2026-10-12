# =============================================================
# app/__init__.py — Application factory
# =============================================================
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db           = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)

    # ── Configuration ──────────────────────────────────────────
    app.config['SECRET_KEY']          = 'cirrhosis-secret-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cirrhosis.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── Initialise extensions ───────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view    = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # ── Register blueprints ─────────────────────────────────────
    from app.routes.auth   import auth
    from app.routes.admin  import admin
    from app.routes.lab    import lab
    from app.routes.medic  import medic

    app.register_blueprint(auth)
    app.register_blueprint(admin,  url_prefix='/admin')
    app.register_blueprint(lab,    url_prefix='/lab')
    app.register_blueprint(medic,  url_prefix='/medic')

    # ── Create tables on first run ──────────────────────────────
    with app.app_context():
        from app.models import User, Patient, Prediction
        db.create_all()
        _seed_users()

    return app


def _seed_users():
    """Create default users if the database is empty."""
    from app.models import User
    from werkzeug.security import generate_password_hash

    if User.query.count() == 0:
        users = [
            User(username='admin',    password=generate_password_hash('admin123'),    role='admin'),
            User(username='labtech',  password=generate_password_hash('lab123'),      role='lab'),
            User(username='medic',    password=generate_password_hash('medic123'),    role='medic'),
        ]
        from app import db
        db.session.add_all(users)
        db.session.commit()
        print("✓ Default users seeded (admin / labtech / medic)")
