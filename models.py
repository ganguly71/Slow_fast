from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Predefined subject list
SUBJECTS = ['C', 'OS', 'COA', 'CN', 'DAA', 'DSA', 'DM']

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='faculty') # 'admin' or 'faculty'
    subjects = db.Column(db.String(200), default='')  # comma-separated: "COA,DSA"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_subjects(self):
        """Return list of assigned subjects."""
        return [s.strip() for s in self.subjects.split(',') if s.strip()] if self.subjects else []

    def set_subjects(self, subject_list):
        """Set subjects from a list."""
        self.subjects = ','.join(subject_list)

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

class AssignmentGroup(db.Model):
    """Represents a single assignment/exam given to a group of students."""
    __tablename__ = 'assignment_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)          # e.g. "Mid-Sem Exam 1"
    subject = db.Column(db.String(100), nullable=False)
    total_marks = db.Column(db.Float, nullable=False)          # maximum marks for this assignment
    date = db.Column(db.DateTime, default=datetime.utcnow)
    remedial_booked = db.Column(db.Boolean, default=False)     # True once "Book Remedial" has been clicked

    assessments = db.relationship('Assessment', backref='assignment_group', lazy=True, cascade="all, delete-orphan")

class Assessment(db.Model):
    __tablename__ = 'assessments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    assignment_group_id = db.Column(db.Integer, db.ForeignKey('assignment_groups.id'), nullable=True)

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
    is_done = db.Column(db.Boolean, default=False)
    faculty = db.relationship('User', backref='remedials_assigned')
