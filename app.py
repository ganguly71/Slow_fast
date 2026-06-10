import os
from flask import Flask
from models import db, User
from flask_login import LoginManager

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key_here'
    
    # Database configuration (support Supabase / Postgres)
    db_url = os.environ.get('DATABASE_URL', '').strip()
    if not db_url:
        db_url = 'sqlite:///database.db'
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'main.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    with app.app_context():
        db.create_all()
        # Lightweight migration: add threshold_percent column if upgrading from old schema
        try:
            db.session.execute(db.text(
                "ALTER TABLE assignment_groups ADD COLUMN threshold_percent FLOAT NOT NULL DEFAULT 50.0"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()  # column already exists
        # Migration: add assignment_group_id to remedial_schedules
        try:
            db.session.execute(db.text(
                "ALTER TABLE remedial_schedules ADD COLUMN assignment_group_id INTEGER REFERENCES assignment_groups(id)"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()  # column already exists
        # Create a default admin if none exists
        if not User.query.filter_by(role='admin').first():
            admin = User(name='Admin', email='admin@example.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
