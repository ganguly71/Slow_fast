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

    def run_migrations():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        required_columns = [
            ("questions", "exam_id", "INTEGER REFERENCES exams(id)"),
            ("questions", "text", "TEXT"),
            ("questions", "marks_awarded", "FLOAT NOT NULL DEFAULT 1.0"),
            ("questions", "marks_deducted", "FLOAT NOT NULL DEFAULT 0.0"),
            ("options", "text", "TEXT"),
            ("options", "is_correct", "BOOLEAN DEFAULT FALSE"),
            ("assignment_groups", "threshold_percent", "FLOAT NOT NULL DEFAULT 50.0"),
            ("remedial_schedules", "assignment_group_id", "INTEGER REFERENCES assignment_groups(id)"),
            ("students", "password_hash", "VARCHAR(255)")
        ]
        
        for table_name, col_name, col_def in required_columns:
            if not inspector.has_table(table_name):
                continue
            columns = [c['name'] for c in inspector.get_columns(table_name)]
            if col_name not in columns:
                try:
                    db.session.execute(db.text(
                        f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                    ))
                    db.session.commit()
                except Exception:
                    db.session.rollback()

        # Legacy columns cleanup to prevent NOT NULL constraint failures
        legacy_cleanup = [
            ("questions", "online_test_id"),
            ("questions", "question_text"),
            ("questions", "positive_marks"),
            ("questions", "negative_marks"),
            ("options", "option_text")
        ]
        for table_name, col_name in legacy_cleanup:
            if inspector.has_table(table_name):
                columns = [c['name'] for c in inspector.get_columns(table_name)]
                if col_name in columns:
                    try:
                        cascade = " CASCADE" if "postgresql" in str(db.engine.url) else ""
                        db.session.execute(db.text(
                            f"ALTER TABLE {table_name} DROP COLUMN {col_name}{cascade}"
                        ))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

    with app.app_context():
        db.create_all()
        run_migrations()
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
