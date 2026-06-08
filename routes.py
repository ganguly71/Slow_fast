from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Student, Assessment, Classification, RemedialSchedule, SUBJECTS
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
    # Count UNIQUE students classified as fast/slow (not per-subject classification rows)
    fast_learners = db.session.query(Classification.student_id).filter_by(
        learner_type='Fast Learner'
    ).distinct().count()
    slow_learners = db.session.query(Classification.student_id).filter_by(
        learner_type='Slow Learner'
    ).distinct().count()
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
        selected_subjects = request.form.getlist('subjects')  # multi-select
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('User with this email already exists.', 'warning')
        else:
            new_user = User(name=name, email=email, role=role)
            new_user.set_password(password)
            new_user.set_subjects(selected_subjects)
            db.session.add(new_user)
            db.session.commit()
            flash('Faculty added successfully.', 'success')
            
    faculty = User.query.all()
    return render_template('manage_faculty.html', faculty=faculty, subjects=SUBJECTS)

def get_next_available_slot():
    # Schedule remedial 3 days from now for simplicity
    return datetime.utcnow() + timedelta(days=3)

def find_faculty_for_subject(subject):
    """Find a faculty member assigned to the given subject."""
    # Search all faculty users whose subjects field contains the subject
    all_faculty = User.query.filter_by(role='faculty').all()
    for fac in all_faculty:
        if subject in fac.get_subjects():
            return fac
    # Also check admins as fallback
    all_admins = User.query.filter_by(role='admin').all()
    for admin in all_admins:
        if subject in admin.get_subjects():
            return admin
    return None

@main.route('/assessments', methods=['GET', 'POST'])
@login_required
def manage_assessments():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        subject = request.form.get('subject')
        marks = float(request.form.get('marks'))
        
        # Validate subject
        if subject not in SUBJECTS:
            flash('Invalid subject selected.', 'danger')
            return redirect(url_for('main.manage_assessments'))
        
        # Validate student exists
        student = Student.query.get(student_id)
        if not student:
            flash('Student not found.', 'danger')
            return redirect(url_for('main.manage_assessments'))
        
        # Record Assessment
        assessment = Assessment(student_id=student_id, subject=subject, marks=marks)
        db.session.add(assessment)
        
        # Classification Logic
        if marks < THRESHOLD_MARKS:
            learner_type = "Slow Learner"
            
            # Find the faculty assigned to this subject
            subject_faculty = find_faculty_for_subject(subject)
            assigned_faculty_id = subject_faculty.id if subject_faculty else current_user.id
            faculty_email = subject_faculty.email if subject_faculty else current_user.email
            
            # Remedial Scheduling
            remedial_date = get_next_available_slot()
            remedial = RemedialSchedule(
                student_id=student_id,
                subject=subject,
                date=remedial_date,
                faculty_id=assigned_faculty_id
            )
            db.session.add(remedial)
            
            # Email Notification to the subject's faculty
            send_remedial_notification(faculty_email, student.name, subject, marks, remedial_date)
            
            faculty_name = subject_faculty.name if subject_faculty else current_user.name
            flash(f'{student.name} classified as Slow Learner. Remedial scheduled and email sent to {faculty_name}.', 'warning')
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
    return render_template('manage_assessments.html', assessments=assessments, students=students, subjects=SUBJECTS)

@main.route('/api/search_student')
@login_required
def search_student():
    """AJAX endpoint: search student by roll number."""
    roll_no = request.args.get('roll_no', '').strip()
    if not roll_no:
        return jsonify([])
    
    # Search for students whose roll_no starts with or contains the query
    students = Student.query.filter(Student.roll_no.ilike(f'%{roll_no}%')).limit(10).all()
    results = [{'id': s.id, 'name': s.name, 'roll_no': s.roll_no} for s in students]
    return jsonify(results)

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
