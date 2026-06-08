from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='faculty') # 'admin' or 'faculty'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    roll_no = db.Column(db.String(50), unique=True, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    
    assessments = db.relationship('Assessment', backref='student', lazy=True, cascade="all, delete-orphan")
    classifications = db.relationship('Classification', backref='student', lazy=True, cascade="all, delete-orphan")
    remedials = db.relationship('RemedialSchedule', backref='student', lazy=True, cascade="all, delete-orphan")

class Assessment(db.Model):
    __tablename__ = 'assessments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Classification(db.Model):
    __tablename__ = 'classifications'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    learner_type = db.Column(db.String(50), nullable=False) # 'Fast Learner' or 'Slow Learner'
    subject = db.Column(db.String(100), nullable=False) # Important to track classification per subject

class RemedialSchedule(db.Model):
    __tablename__ = 'remedial_schedules'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    faculty = db.relationship('User', backref='remedials_assigned')
