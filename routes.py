from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Student, Assessment, Classification, RemedialSchedule
from mail_service import send_remedial_notification
from datetime import datetime, timedelta

main = Blueprint('main', __name__)

THRESHOLD_MARKS = 50.0

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/dashboard')
@login_required
def dashboard():
    total_students = Student.query.count()
    fast_learners = Classification.query.filter_by(learner_type='Fast Learner').count()
    slow_learners = Classification.query.filter_by(learner_type='Slow Learner').count()
    upcoming_remedials = RemedialSchedule.query.filter(RemedialSchedule.date >= datetime.utcnow()).count()
    
    return render_template('dashboard.html', 
                           total_students=total_students,
                           fast_learners=fast_learners,
                           slow_learners=slow_learners,
                           upcoming_remedials=upcoming_remedials)

@main.route('/students', methods=['GET', 'POST'])
@login_required
def manage_students():
    if request.method == 'POST':
        name = request.form.get('name')
        roll_no = request.form.get('roll_no')
        semester = request.form.get('semester')
        department = request.form.get('department')
        
        existing_student = Student.query.filter_by(roll_no=roll_no).first()
        if existing_student:
            flash('Student with this Roll No already exists.', 'warning')
        else:
            new_student = Student(name=name, roll_no=roll_no, semester=int(semester), department=department)
            db.session.add(new_student)
            db.session.commit()
            flash('Student added successfully.', 'success')
            
    students = Student.query.all()
    return render_template('manage_students.html', students=students)

@main.route('/faculty', methods=['GET', 'POST'])
@login_required
def manage_faculty():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'faculty')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('User with this email already exists.', 'warning')
        else:
            new_user = User(name=name, email=email, role=role)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Faculty added successfully.', 'success')
            
    faculty = User.query.all()
    return render_template('manage_faculty.html', faculty=faculty)

def get_next_available_slot():
    # Schedule remedial 3 days from now for simplicity
    return datetime.utcnow() + timedelta(days=3)

@main.route('/assessments', methods=['GET', 'POST'])
@login_required
def manage_assessments():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        subject = request.form.get('subject')
        marks = float(request.form.get('marks'))
        
        # Record Assessment
        assessment = Assessment(student_id=student_id, subject=subject, marks=marks)
        db.session.add(assessment)
        
        # Classification Logic
        student = Student.query.get(student_id)
        if marks < THRESHOLD_MARKS:
            learner_type = "Slow Learner"
            
            # Remedial Scheduling
            remedial_date = get_next_available_slot()
            remedial = RemedialSchedule(
                student_id=student_id,
                subject=subject,
                date=remedial_date,
                faculty_id=current_user.id
            )
            db.session.add(remedial)
            
            # Email Notification
            send_remedial_notification(current_user.email, student.name, subject, marks, remedial_date)
            flash(f'{student.name} classified as Slow Learner. Remedial scheduled and email sent.', 'warning')
        else:
            learner_type = "Fast Learner"
            flash(f'{student.name} classified as Fast Learner.', 'success')
            
        # Update or Create Classification
        classification = Classification.query.filter_by(student_id=student_id, subject=subject).first()
        if classification:
            classification.learner_type = learner_type
        else:
            classification = Classification(student_id=student_id, subject=subject, learner_type=learner_type)
            db.session.add(classification)
            
        db.session.commit()
        return redirect(url_for('main.manage_assessments'))
        
    assessments = Assessment.query.order_by(Assessment.date.desc()).all()
    students = Student.query.all()
    return render_template('manage_assessments.html', assessments=assessments, students=students)

@main.route('/remedials')
@login_required
def remedial_schedules():
    if current_user.role == 'admin':
        schedules = RemedialSchedule.query.all()
    else:
        schedules = RemedialSchedule.query.filter_by(faculty_id=current_user.id).all()
        
    return render_template('remedial_schedules.html', schedules=schedules)

@main.route('/reports')
@login_required
def reports():
    fast_learners = Classification.query.filter_by(learner_type='Fast Learner').all()
    slow_learners = Classification.query.filter_by(learner_type='Slow Learner').all()
    return render_template('reports.html', fast_learners=fast_learners, slow_learners=slow_learners)
