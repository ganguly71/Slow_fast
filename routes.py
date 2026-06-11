from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Student, Assessment, Classification, RemedialSchedule, AssignmentGroup, SUBJECTS
from mail_service import send_remedial_notification, send_remedial_batch_notification
from datetime import datetime, timedelta
from sqlalchemy import func

main = Blueprint('main', __name__)

THRESHOLD_PERCENT = 50.0  # percentage threshold for slow/fast learner

@main.before_request
def restrict_access():
    if not request.endpoint:
        return
    if current_user.is_authenticated:
        if isinstance(current_user, Student) or current_user.get_id().startswith('student_'):
            allowed_for_students = [
                'main.index',
                'main.student_login',
                'main.student_tests',
                'main.take_test',
                'main.submit_test',
                'main.logout',
                'main.test_status',
                'static'
            ]
            if request.endpoint not in allowed_for_students:
                flash('Access Denied: You do not have permission to access that page.', 'danger')
                return redirect(url_for('main.student_tests'))
        else:
            # Faculty/Admin cannot attempt student tests
            student_only = [
                'main.student_tests',
                'main.take_test',
                'main.submit_test'
            ]
            if request.endpoint in student_only:
                flash('Access Denied: Faculty/Admin cannot access student tests.', 'danger')
                return redirect(url_for('main.dashboard'))

@main.route('/')
def index():
    if current_user.is_authenticated:
        if isinstance(current_user, Student) or current_user.get_id().startswith('student_'):
            return redirect(url_for('main.student_tests'))
        return redirect(url_for('main.dashboard'))
    return render_template('landing.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if isinstance(current_user, Student) or current_user.get_id().startswith('student_'):
            return redirect(url_for('main.student_tests'))
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

@main.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if current_user.is_authenticated:
        if isinstance(current_user, Student) or current_user.get_id().startswith('student_'):
            return redirect(url_for('main.student_tests'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        roll_no = request.form.get('roll_no', '').strip()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')

        student = Student.query.filter_by(roll_no=roll_no).first()
        if not student:
            flash('Student with this Roll No is not pre-registered. Please contact your instructor.', 'danger')
            return render_template('student_login.html')

        # Check if first-time login (no password set)
        if not student.password_hash:
            if not name:
                flash('First-time login: Full Name is required to verify your identity.', 'warning')
                return render_template('student_login.html')
            # Verify name (case-insensitive)
            if student.name.strip().lower() != name.lower():
                flash('Name does not match pre-registered record for this Roll No. Please enter your name exactly as registered.', 'danger')
                return render_template('student_login.html')
            
            # Setup password
            student.set_password(password)
            db.session.commit()
            login_user(student)
            flash(f'Welcome {student.name}! Your account has been registered successfully.', 'success')
            return redirect(url_for('main.student_tests'))
        else:
            # Subsequent login
            if student.check_password(password):
                login_user(student)
                flash(f'Welcome back, {student.name}!', 'success')
                return redirect(url_for('main.student_tests'))
            else:
                flash('Incorrect password. Please try again or contact Admin to reset it.', 'danger')

    return render_template('student_login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))


# ─── Dashboard (Feature 1: Overhauled with interactive charts) ────────────────

@main.route('/dashboard')
@login_required
def dashboard():
    total_students = Student.query.count()
    total_assignments = AssignmentGroup.query.count()
    upcoming_remedials = RemedialSchedule.query.filter(RemedialSchedule.date >= datetime.utcnow()).count()

    # Avg attendance: for each assignment, how many students appeared (marks != -1) vs total selected
    all_groups = AssignmentGroup.query.all()
    total_appeared = 0
    total_selected = 0
    for g in all_groups:
        for a in g.assessments:
            total_selected += 1
            if a.marks != -1:
                total_appeared += 1
    avg_attendance = round((total_appeared / total_selected * 100), 1) if total_selected > 0 else 0

    # Students per department
    dept_rows = db.session.query(Student.department, func.count(Student.id)).group_by(Student.department).all()
    dept_labels = [r[0] for r in dept_rows]
    dept_counts = [r[1] for r in dept_rows]

    # Students per semester
    sem_rows = db.session.query(Student.semester, func.count(Student.id)).group_by(Student.semester).order_by(Student.semester).all()
    sem_labels = [f"Sem {r[0]}" for r in sem_rows]
    sem_counts = [r[1] for r in sem_rows]

    # Assignments per subject
    subj_rows = db.session.query(AssignmentGroup.subject, func.count(AssignmentGroup.id)).group_by(AssignmentGroup.subject).all()
    subj_labels = [r[0] for r in subj_rows]
    subj_counts = [r[1] for r in subj_rows]

    # Average score per subject (excluding absent marks = -1)
    avg_score_rows = db.session.query(
        AssignmentGroup.subject,
        func.avg(Assessment.marks)
    ).join(Assessment, Assessment.assignment_group_id == AssignmentGroup.id
    ).filter(Assessment.marks != -1
    ).group_by(AssignmentGroup.subject).all()
    avg_score_labels = [r[0] for r in avg_score_rows]
    avg_score_values = [round(r[1], 1) if r[1] else 0 for r in avg_score_rows]

    return render_template('dashboard.html',
                           total_students=total_students,
                           total_assignments=total_assignments,
                           avg_attendance=avg_attendance,
                           upcoming_remedials=upcoming_remedials,
                           dept_labels=dept_labels,
                           dept_counts=dept_counts,
                           sem_labels=sem_labels,
                           sem_counts=sem_counts,
                           subj_labels=subj_labels,
                           subj_counts=subj_counts,
                           avg_score_labels=avg_score_labels,
                           avg_score_values=avg_score_values)


# ─── Student Routes ──────────────────────────────────────────────────────────

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

@main.route('/students/edit/<int:student_id>', methods=['POST'])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    name = request.form.get('name')
    roll_no = request.form.get('roll_no')
    semester = request.form.get('semester')
    department = request.form.get('department')
    password = request.form.get('password')
    
    existing = Student.query.filter(Student.roll_no == roll_no, Student.id != student_id).first()
    if existing:
        flash('Another student already has this Roll No.', 'danger')
    else:
        student.name = name
        student.roll_no = roll_no
        student.semester = int(semester)
        student.department = department
        
        if password:
            if current_user.role == 'admin':
                student.set_password(password)
                flash('Student details and password updated successfully.', 'success')
            else:
                flash('Student details updated, but password reset is restricted to admins only.', 'warning')
        else:
            flash('Student details updated successfully.', 'success')
            
        db.session.commit()
        
    return redirect(url_for('main.manage_students'))

@main.route('/students/delete/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully.', 'success')
    return redirect(url_for('main.manage_students'))

@main.route('/students/import', methods=['POST'])
@login_required
def import_students():
    import csv
    import io
    
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('main.manage_students'))
        
    filename = file.filename.lower()
    rows = []
    
    try:
        if filename.endswith('.csv'):
            stream = io.StringIO(file.read().decode("utf8"), newline=None)
            reader = csv.reader(stream)
            rows = list(reader)
        elif filename.endswith(('.xls', '.xlsx')):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file.read()), data_only=True)
            sheet = wb.active
            rows = [[cell.value for cell in row] for row in sheet.iter_rows()]
        else:
            flash('Unsupported file format. Please upload an Excel (.xlsx) or CSV file.', 'danger')
            return redirect(url_for('main.manage_students'))
    except Exception as e:
        flash(f'Error reading file: {str(e)}', 'danger')
        return redirect(url_for('main.manage_students'))
        
    if not rows or len(rows) < 2:
        flash('The file is empty or missing data.', 'danger')
        return redirect(url_for('main.manage_students'))
        
    # Get header and clean it
    headers = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    data_rows = rows[1:]
    
    col_mapping = {}
    for idx, col in enumerate(headers):
        if col in ['name', 'student name', 'student_name']:
            col_mapping['name'] = idx
        elif col in ['roll', 'roll no', 'roll_no', 'rollno', 'roll number']:
            col_mapping['roll_no'] = idx
        elif col in ['sem', 'semester']:
            col_mapping['semester'] = idx
        elif col in ['dept', 'department', 'branch']:
            col_mapping['department'] = idx
            
    required_cols = ['name', 'roll_no', 'semester', 'department']
    missing = [col for col in required_cols if col not in col_mapping]
    
    if missing:
        flash(f'Missing required columns in sheet: {", ".join(missing)}. Detected columns: {", ".join(headers)}', 'danger')
        return redirect(url_for('main.manage_students'))
        
    added_count = 0
    updated_count = 0
    
    for row in data_rows:
        if len(row) <= max(col_mapping.values()):
            continue
            
        name_val = str(row[col_mapping['name']]).strip() if row[col_mapping['name']] is not None else ""
        roll_val = str(row[col_mapping['roll_no']]).strip() if row[col_mapping['roll_no']] is not None else ""
        
        try:
            sem_val = int(float(str(row[col_mapping['semester']]).strip()))
        except (ValueError, TypeError):
            sem_val = 1
            
        dept_val = str(row[col_mapping['department']]).strip() if row[col_mapping['department']] is not None else ""
        
        if not name_val or not roll_val:
            continue
            
        student = Student.query.filter_by(roll_no=roll_val).first()
        if student:
            student.name = name_val
            student.semester = sem_val
            student.department = dept_val
            updated_count += 1
        else:
            new_student = Student(name=name_val, roll_no=roll_val, semester=sem_val, department=dept_val)
            db.session.add(new_student)
            added_count += 1
            
    db.session.commit()
    flash(f'Successfully imported students: {added_count} added, {updated_count} updated.', 'success')
    return redirect(url_for('main.manage_students'))


# ─── Student Detail (Feature 3) ──────────────────────────────────────────────

@main.route('/students/<int:student_id>/detail')
@login_required
def student_detail(student_id):
    student = Student.query.get_or_404(student_id)
    assessments = Assessment.query.filter_by(student_id=student.id).order_by(Assessment.date.desc()).all()

    total_assignments = len(assessments)
    absent_count = sum(1 for a in assessments if a.marks == -1)
    present_assessments = [a for a in assessments if a.marks != -1]

    if present_assessments:
        avg_percentage = round(
            sum((a.marks / a.assignment_group.total_marks * 100) for a in present_assessments if a.assignment_group) /
            len([a for a in present_assessments if a.assignment_group]),
            1
        ) if any(a.assignment_group for a in present_assessments) else 0
    else:
        avg_percentage = 0

    # Build per-assignment detail list
    assignment_details = []
    for a in assessments:
        group = a.assignment_group
        if a.marks == -1:
            status = 'Absent'
            pct = None
        elif group:
            pct = round(a.marks / group.total_marks * 100, 1) if group.total_marks > 0 else 0
            threshold = group.threshold_percent
            status = 'Slow Learner' if pct < threshold else 'Fast Learner'
        else:
            pct = None
            status = 'N/A'

        assignment_details.append({
            'name': group.name if group else 'Unknown',
            'subject': a.subject,
            'marks': a.marks,
            'total_marks': group.total_marks if group else '?',
            'percentage': pct,
            'status': status,
            'date': a.date
        })

    return render_template('student_detail.html',
                           student=student,
                           total_assignments=total_assignments,
                           absent_count=absent_count,
                           present_count=total_assignments - absent_count,
                           avg_percentage=avg_percentage,
                           assignment_details=assignment_details)


# ─── Faculty Routes ──────────────────────────────────────────────────────────

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

@main.route('/faculty/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_faculty(user_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role', 'faculty')
        selected_subjects = request.form.getlist('subjects')
        password = request.form.get('password')
        
        # Check if email is already taken by another user
        existing_user = User.query.filter(User.email == email, User.id != user_id).first()
        if existing_user:
            flash('Another user with this email already exists.', 'warning')
        else:
            user.name = name
            user.email = email
            if user.id != current_user.id:  # Protect current admin from losing admin role
                user.role = role
            user.set_subjects(selected_subjects)
            
            if password:
                user.set_password(password)
                
            db.session.commit()
            flash('Faculty details updated successfully.', 'success')
            return redirect(url_for('main.manage_faculty'))
            
    return render_template('edit_faculty.html', user=user, subjects=SUBJECTS)

@main.route('/faculty/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_faculty(user_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('Faculty deleted successfully.', 'success')
        
    return redirect(url_for('main.manage_faculty'))

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


# ─── Assessment Routes (Feature 2: Absent support + Feature 4: Stats) ────────

@main.route('/assessments', methods=['GET', 'POST'])
@login_required
def manage_assessments():
    if request.method == 'POST':
        assignment_name = request.form.get('assignment_name', '').strip()
        subject = request.form.get('subject')
        total_marks = request.form.get('total_marks')
        threshold_input = request.form.get('threshold_percent', '').strip()

        # Validate
        if not assignment_name:
            flash('Assignment name is required.', 'danger')
            return redirect(url_for('main.manage_assessments'))
        if subject not in SUBJECTS:
            flash('Invalid subject selected.', 'danger')
            return redirect(url_for('main.manage_assessments'))
        try:
            total_marks = float(total_marks)
            if total_marks <= 0:
                raise ValueError
        except (TypeError, ValueError):
            flash('Total marks must be a positive number.', 'danger')
            return redirect(url_for('main.manage_assessments'))

        # Parse threshold — default to 50% if not provided or invalid
        try:
            threshold_percent = float(threshold_input)
            if threshold_percent < 0 or threshold_percent > 100:
                threshold_percent = 50.0
        except (TypeError, ValueError):
            threshold_percent = 50.0

        # Gather per-student marks from form (keys like "marks_<student_id>")
        student_ids = request.form.getlist('student_ids')  # hidden inputs listing selected students
        if not student_ids:
            flash('Please select at least one student.', 'danger')
            return redirect(url_for('main.manage_assessments'))

        # Create the assignment group
        group = AssignmentGroup(
            name=assignment_name,
            subject=subject,
            total_marks=total_marks,
            threshold_percent=threshold_percent
        )
        db.session.add(group)
        db.session.flush()  # get group.id

        added_count = 0
        for sid in student_ids:
            student = Student.query.get(int(sid))
            if not student:
                continue
            marks_val = request.form.get(f'marks_{sid}', '').strip()
            if not marks_val:
                continue

            # Feature 2: Accept 'A' or 'a' for absent → store as -1
            if marks_val.upper() == 'A':
                marks = -1
            else:
                try:
                    marks = float(marks_val)
                except ValueError:
                    continue

            assessment = Assessment(
                student_id=student.id,
                subject=subject,
                marks=marks,
                assignment_group_id=group.id
            )
            db.session.add(assessment)
            added_count += 1

        db.session.commit()
        flash(f'Assignment "{assignment_name}" created with {added_count} student(s).', 'success')
        return redirect(url_for('main.manage_assessments'))

    # GET — show assignment groups
    groups = AssignmentGroup.query.order_by(AssignmentGroup.date.desc()).all()
    students = Student.query.order_by(Student.roll_no).all()
    departments = sorted(set(s.department for s in students if s.department))
    faculty_members = User.query.filter_by(role='faculty').all()
    # also add admin if admin is acting as faculty, but usually all users can teach in this app
    all_users = User.query.all()
    return render_template('manage_assessments.html',
                           groups=groups,
                           students=students,
                           subjects=SUBJECTS,
                           departments=departments,
                           all_users=all_users)


@main.route('/assessments/book_remedial/<int:group_id>', methods=['POST'])
@login_required
def book_remedial(group_id):
    """Identify slow learners in this assignment group, create remedial
    schedules, update classifications, and send ONE consolidated email
    to the subject faculty. Absent students are listed separately."""
    group = AssignmentGroup.query.get_or_404(group_id)

    if group.remedial_booked:
        flash('Remedial has already been booked for this assignment.', 'warning')
        return redirect(url_for('main.manage_assessments'))

    threshold = (group.threshold_percent / 100.0) * group.total_marks
    
    faculty_id_str = request.form.get('faculty_id')
    if not faculty_id_str:
        flash('Please select a faculty member.', 'danger')
        return redirect(url_for('main.manage_assessments'))
        
    selected_faculty = User.query.get_or_404(int(faculty_id_str))
    assigned_faculty_id = selected_faculty.id
    faculty_email = selected_faculty.email
    faculty_name = selected_faculty.name

    remedial_date = get_next_available_slot()
    slow_students = []
    absent_students = []

    for assessment in group.assessments:
        student = assessment.student

        # Feature 2: Handle absent students (marks == -1)
        if assessment.marks == -1:
            absent_students.append({
                'name': student.name,
                'roll_no': student.roll_no,
            })
            continue  # Don't classify absent students

        if assessment.marks < threshold:
            learner_type = "Slow Learner"

            # Create remedial schedule (Feature 5: link to assignment_group)
            remedial = RemedialSchedule(
                student_id=student.id,
                subject=group.subject,
                date=remedial_date,
                faculty_id=assigned_faculty_id,
                assignment_group_id=group.id
            )
            db.session.add(remedial)

            slow_students.append({
                'name': student.name,
                'roll_no': student.roll_no,
                'marks': assessment.marks
            })
        else:
            learner_type = "Fast Learner"

        # Update or create classification
        classification = Classification.query.filter_by(
            student_id=student.id, subject=group.subject
        ).first()
        if classification:
            classification.learner_type = learner_type
        else:
            classification = Classification(
                student_id=student.id,
                subject=group.subject,
                learner_type=learner_type
            )
            db.session.add(classification)

    group.remedial_booked = True
    db.session.commit()

    if slow_students or absent_students:
        # Send one consolidated email with separate absent list
        send_remedial_batch_notification(
            faculty_email, group.name, group.subject, slow_students, remedial_date,
            absent_list=absent_students
        )
        msg_parts = []
        if slow_students:
            msg_parts.append(f'{len(slow_students)} slow learner(s)')
        if absent_students:
            msg_parts.append(f'{len(absent_students)} absent student(s)')
        flash(
            f'Remedial booked for {" and ".join(msg_parts)}. '
            f'Email sent to {faculty_name}.',
            'warning'
        )
    else:
        flash('No slow learners found in this assignment — no remedial needed!', 'success')

    return redirect(url_for('main.manage_assessments'))


@main.route('/assessments/delete/<int:group_id>', methods=['POST'])
@login_required
def delete_assignment(group_id):
    group = AssignmentGroup.query.get_or_404(group_id)
    # Manually delete remedials to avoid FK constraints if cascade isn't fully set up on both sides
    RemedialSchedule.query.filter_by(assignment_group_id=group.id).delete()
    db.session.delete(group)
    db.session.commit()
    flash(f'Assignment "{group.name}" deleted successfully.', 'success')
    return redirect(url_for('main.manage_assessments'))


@main.route('/assessments/edit_threshold/<int:group_id>', methods=['POST'])
@login_required
def edit_threshold(group_id):
    group = AssignmentGroup.query.get_or_404(group_id)
    try:
        new_threshold = float(request.form.get('threshold_percent', group.threshold_percent))
        if new_threshold < 0 or new_threshold > 100:
            flash('Threshold percentage must be between 0 and 100.', 'danger')
            return redirect(url_for('main.manage_assessments'))
    except ValueError:
        flash('Invalid threshold percentage.', 'danger')
        return redirect(url_for('main.manage_assessments'))

    group.threshold_percent = new_threshold
    db.session.commit()

    # Re-evaluate all students' classifications and remedials
    threshold_marks = (new_threshold / 100.0) * group.total_marks
    changes_made = 0

    sibling_remedial = RemedialSchedule.query.filter_by(assignment_group_id=group.id).first()
    remedial_date = sibling_remedial.date if sibling_remedial else get_next_available_slot()
    if sibling_remedial:
        assigned_faculty_id = sibling_remedial.faculty_id
    else:
        subject_faculty = find_faculty_for_subject(group.subject)
        assigned_faculty_id = subject_faculty.id if subject_faculty else current_user.id

    for assessment in group.assessments:
        student = assessment.student
        new_marks = assessment.marks

        if new_marks == -1.0:
            learner_type = None
        elif new_marks < threshold_marks:
            learner_type = "Slow Learner"
        else:
            learner_type = "Fast Learner"

        if learner_type:
            classification = Classification.query.filter_by(
                student_id=student.id, subject=group.subject
            ).first()
            if classification:
                classification.learner_type = learner_type
            else:
                classification = Classification(
                    student_id=student.id,
                    subject=group.subject,
                    learner_type=learner_type
                )
                db.session.add(classification)

        if group.remedial_booked:
            existing_remedial = RemedialSchedule.query.filter_by(
                student_id=student.id,
                assignment_group_id=group.id
            ).first()

            if new_marks == -1.0 or new_marks >= threshold_marks:
                if existing_remedial:
                    db.session.delete(existing_remedial)
                    changes_made += 1
            else:
                if not existing_remedial:
                    new_remedial = RemedialSchedule(
                        student_id=student.id,
                        subject=group.subject,
                        date=remedial_date,
                        faculty_id=assigned_faculty_id,
                        assignment_group_id=group.id
                    )
                    db.session.add(new_remedial)
                    changes_made += 1

    db.session.commit()
    msg = f'Threshold updated to {new_threshold}% for "{group.name}".'
    if group.remedial_booked and changes_made > 0:
        msg += f' {changes_made} remedial schedule change(s) synced.'
    flash(msg, 'success')
    return redirect(url_for('main.manage_assessments'))


# ─── Assignment Stats API (Feature 4) ────────────────────────────────────────

@main.route('/api/assignment_stats/<int:group_id>')
@login_required
def assignment_stats(group_id):
    """Return JSON stats for an assignment group."""
    group = AssignmentGroup.query.get_or_404(group_id)
    threshold = (group.threshold_percent / 100.0) * group.total_marks

    slow = []
    fast = []
    absent = []
    total_marks_sum = 0
    present_count = 0

    for a in group.assessments:
        student = a.student
        entry = {
            'name': student.name,
            'roll_no': student.roll_no,
            'marks': a.marks,
            'department': student.department
        }
        if a.marks == -1:
            entry['percentage'] = None
            absent.append(entry)
        else:
            pct = round(a.marks / group.total_marks * 100, 1) if group.total_marks > 0 else 0
            entry['percentage'] = pct
            total_marks_sum += a.marks
            present_count += 1
            if a.marks < threshold:
                slow.append(entry)
            else:
                fast.append(entry)

    avg_score = round(total_marks_sum / present_count, 2) if present_count > 0 else 0
    avg_percentage = round(avg_score / group.total_marks * 100, 1) if group.total_marks > 0 and present_count > 0 else 0

    return jsonify({
        'assignment_name': group.name,
        'subject': group.subject,
        'total_marks': group.total_marks,
        'threshold_percent': group.threshold_percent,
        'threshold_marks': threshold,
        'total_students': len(group.assessments),
        'slow_count': len(slow),
        'fast_count': len(fast),
        'absent_count': len(absent),
        'avg_score': avg_score,
        'avg_percentage': avg_percentage,
        'slow_learners': slow,
        'fast_learners': fast,
        'absent_students': absent
    })


@main.route('/assessments/edit_marks/<int:assessment_id>', methods=['POST'])
@login_required
def edit_assessment_marks(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    group = assessment.assignment_group
    if not group:
        flash('Assignment group not found for this assessment.', 'danger')
        return redirect(url_for('main.manage_assessments'))

    marks_val = request.form.get('marks', '').strip()
    if not marks_val:
        flash('Marks field cannot be empty.', 'danger')
        return redirect(url_for('main.manage_assessments'))

    if marks_val.upper() == 'A':
        new_marks = -1.0
    else:
        try:
            new_marks = float(marks_val)
            if new_marks < 0:
                flash('Marks cannot be negative.', 'danger')
                return redirect(url_for('main.manage_assessments'))
            if new_marks > group.total_marks:
                flash(f'Marks cannot exceed the total marks of {group.total_marks}.', 'danger')
                return redirect(url_for('main.manage_assessments'))
        except ValueError:
            flash('Invalid marks input. Enter a number or "A" for absent.', 'danger')
            return redirect(url_for('main.manage_assessments'))

    # Update assessment marks
    assessment.marks = new_marks
    db.session.commit()

    # Re-evaluate learner type and remedial schedule if remedial was already booked
    student = assessment.student
    threshold = (group.threshold_percent / 100.0) * group.total_marks

    # 1. Determine classification type based on this assignment update
    if new_marks == -1.0:
        learner_type = None
    elif new_marks < threshold:
        learner_type = "Slow Learner"
    else:
        learner_type = "Fast Learner"

    # 2. Update Classification table (if we have a valid classification type)
    if learner_type:
        classification = Classification.query.filter_by(
            student_id=student.id, subject=group.subject
        ).first()
        if classification:
            classification.learner_type = learner_type
        else:
            classification = Classification(
                student_id=student.id,
                subject=group.subject,
                learner_type=learner_type
            )
            db.session.add(classification)

    # 3. Synchronize RemedialSchedule if remedial_booked is True
    if group.remedial_booked:
        existing_remedial = RemedialSchedule.query.filter_by(
            student_id=student.id,
            assignment_group_id=group.id
        ).first()

        if new_marks == -1.0 or new_marks >= threshold:
            # If absent or fast learner, delete any existing remedial schedule for this assignment
            if existing_remedial:
                db.session.delete(existing_remedial)
                flash(f"Updated marks for {student.name}. Booked remedial schedule has been removed.", 'success')
            else:
                flash(f"Updated marks for {student.name}.", 'success')
        else:
            # If slow learner, make sure a remedial schedule exists for this assignment
            if not existing_remedial:
                # Find date and faculty from other remedial schedules in the same group, if any
                sibling_remedial = RemedialSchedule.query.filter_by(
                    assignment_group_id=group.id
                ).first()
                if sibling_remedial:
                    remedial_date = sibling_remedial.date
                    assigned_faculty_id = sibling_remedial.faculty_id
                else:
                    remedial_date = get_next_available_slot()
                    subject_faculty = find_faculty_for_subject(group.subject)
                    assigned_faculty_id = subject_faculty.id if subject_faculty else current_user.id

                new_remedial = RemedialSchedule(
                    student_id=student.id,
                    subject=group.subject,
                    date=remedial_date,
                    faculty_id=assigned_faculty_id,
                    assignment_group_id=group.id
                )
                db.session.add(new_remedial)
                flash(f"Updated marks for {student.name}. Added to booked remedial schedule.", 'success')
            else:
                flash(f"Updated marks for {student.name}.", 'success')
    else:
        flash(f"Updated marks for {student.name}.", 'success')

    db.session.commit()
    return redirect(url_for('main.manage_assessments'))


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


@main.route('/api/all_students')
@login_required
def all_students_api():
    """Return all students as JSON for the multi-select picker."""
    students = Student.query.order_by(Student.roll_no).all()
    results = [{'id': s.id, 'name': s.name, 'roll_no': s.roll_no, 'department': s.department} for s in students]
    return jsonify(results)


# ─── Remedial Routes (Feature 5: Grouped by assignment) ──────────────────────

@main.route('/remedials')
@login_required
def remedial_schedules():
    if current_user.role == 'admin':
        schedules = RemedialSchedule.query.all()
    else:
        schedules = RemedialSchedule.query.filter_by(faculty_id=current_user.id).all()

    # Group schedules by (assignment_group_id, subject, date, faculty_id)
    grouped = {}
    for s in schedules:
        key = (s.assignment_group_id, s.subject, s.date.strftime('%Y-%m-%d %H:%M'), s.faculty_id)
        if key not in grouped:
            grouped[key] = {
                'assignment_group_id': s.assignment_group_id,
                'assignment_name': s.assignment_group.name if s.assignment_group else 'Legacy',
                'subject': s.subject,
                'date': s.date,
                'faculty_name': s.faculty.name,
                'faculty_id': s.faculty_id,
                'students': [],
                'all_done': True,
                'schedule_ids': []
            }
        grouped[key]['students'].append({
            'name': s.student.name,
            'roll_no': s.student.roll_no,
            'is_done': s.is_done,
            'schedule_id': s.id
        })
        grouped[key]['schedule_ids'].append(s.id)
        if not s.is_done:
            grouped[key]['all_done'] = False

    # Sort by date desc
    remedial_groups = sorted(grouped.values(), key=lambda x: x['date'], reverse=True)

    return render_template('remedial_schedules.html', remedial_groups=remedial_groups)


@main.route('/remedials/toggle_done/<int:schedule_id>', methods=['POST'])
@login_required
def toggle_remedial_done(schedule_id):
    """Toggle the is_done status of a remedial schedule entry."""
    schedule = RemedialSchedule.query.get_or_404(schedule_id)
    schedule.is_done = not schedule.is_done
    db.session.commit()
    status = "Done" if schedule.is_done else "Pending"
    flash(f'Remedial #{schedule.id} marked as {status}.', 'success')
    return redirect(url_for('main.remedial_schedules'))


@main.route('/remedials/toggle_group_done', methods=['POST'])
@login_required
def toggle_group_done():
    """Toggle all remedial entries in a group as done/pending."""
    schedule_ids = request.form.getlist('schedule_ids')
    mark_as = request.form.get('mark_as', 'done')

    for sid in schedule_ids:
        schedule = RemedialSchedule.query.get(int(sid))
        if schedule:
            schedule.is_done = (mark_as == 'done')
    db.session.commit()
    flash(f'All remedials in this class marked as {"Done" if mark_as == "done" else "Pending"}.', 'success')
    return redirect(url_for('main.remedial_schedules'))


@main.route('/reports')
@login_required
def reports():
    fast_learners = Classification.query.filter_by(learner_type='Fast Learner').all()
    slow_learners = Classification.query.filter_by(learner_type='Slow Learner').all()
    return render_template('reports.html', fast_learners=fast_learners, slow_learners=slow_learners)


@main.route('/online_tests', methods=['GET', 'POST'])
@login_required
def manage_online_tests():
    if current_user.get_id().startswith('student_'):
        flash('Access Denied.', 'danger')
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject')
        duration_minutes = request.form.get('duration_minutes')
        threshold_percent = request.form.get('threshold_percent', '50.0')

        if not name or not subject or not duration_minutes:
            flash('All fields are required.', 'danger')
            return redirect(url_for('main.manage_online_tests'))

        try:
            dur = int(duration_minutes)
            thresh = float(threshold_percent)
            if dur <= 0 or thresh < 0 or thresh > 100:
                raise ValueError
        except ValueError:
            flash('Invalid input numbers.', 'danger')
            return redirect(url_for('main.manage_online_tests'))

        test = OnlineTest(
            name=name,
            subject=subject,
            duration_minutes=dur,
            threshold_percent=thresh,
            created_by_id=current_user.id
        )
        db.session.add(test)
        db.session.commit()
        flash(f'Online test "{name}" created successfully.', 'success')
        return redirect(url_for('main.manage_online_tests'))

    tests = OnlineTest.query.order_by(OnlineTest.date_created.desc()).all()
    return render_template('manage_online_tests.html', tests=tests, subjects=SUBJECTS)


@main.route('/online_tests/<int:test_id>/toggle_start', methods=['POST'])
@login_required
def toggle_online_test_start(test_id):
    if current_user.get_id().startswith('student_'):
        flash('Access Denied.', 'danger')
        return redirect(url_for('main.index'))
        
    test = OnlineTest.query.get_or_404(test_id)
    test.start_allowed = not test.start_allowed
    db.session.commit()
    status = "started (active)" if test.start_allowed else "stopped (closed)"
    flash(f'Online test "{test.name}" is now {status}.', 'success')
    return redirect(url_for('main.manage_online_tests'))


@main.route('/api/test_status/<int:test_id>')
@login_required
def test_status(test_id):
    """AJAX endpoint for student attempt screen to poll if the teacher ended the test."""
    test = OnlineTest.query.get_or_404(test_id)
    return jsonify({'active': test.start_allowed})


@main.route('/online_tests/<int:test_id>/delete', methods=['POST'])
@login_required
def delete_online_test(test_id):
    if current_user.get_id().startswith('student_'):
        flash('Access Denied.', 'danger')
        return redirect(url_for('main.index'))
        
    test = OnlineTest.query.get_or_404(test_id)
    db.session.delete(test)
    db.session.commit()
    flash(f'Online test "{test.name}" deleted successfully.', 'success')
    return redirect(url_for('main.manage_online_tests'))


@main.route('/online_tests/<int:test_id>/edit_questions', methods=['GET', 'POST'])
@login_required
def edit_online_test_questions(test_id):
    if current_user.get_id().startswith('student_'):
        flash('Access Denied.', 'danger')
        return redirect(url_for('main.index'))
        
    test = OnlineTest.query.get_or_404(test_id)

    if request.method == 'POST':
        question_text = request.form.get('question_text', '').strip()
        positive_marks = request.form.get('positive_marks')
        negative_marks = request.form.get('negative_marks')

        if not question_text or not positive_marks or not negative_marks:
            flash('Question text and marks are required.', 'danger')
            return redirect(url_for('main.edit_online_test_questions', test_id=test_id))

        try:
            pos_m = float(positive_marks)
            neg_m = float(negative_marks)
            if pos_m < 0 or neg_m < 0:
                raise ValueError
        except ValueError:
            flash('Marks must be positive numbers.', 'danger')
            return redirect(url_for('main.edit_online_test_questions', test_id=test_id))

        # Build question
        question = Question(
            online_test_id=test.id,
            question_text=question_text,
            positive_marks=pos_m,
            negative_marks=neg_m
        )
        db.session.add(question)
        db.session.flush() # get question.id

        # Extract options dynamically
        idx = 0
        while True:
            text_key = f'option_text_{idx}'
            correct_key = f'option_correct_{idx}'
            if text_key not in request.form:
                break
            opt_text = request.form.get(text_key, '').strip()
            is_corr = request.form.get(correct_key) == 'true'
            
            if opt_text:
                option = Option(
                    question_id=question.id,
                    option_text=opt_text,
                    is_correct=is_corr
                )
                db.session.add(option)
            idx += 1

        db.session.commit()
        flash('Question saved successfully.', 'success')
        return redirect(url_for('main.edit_online_test_questions', test_id=test_id))

    return render_template('edit_questions.html', test=test)


@main.route('/online_tests/<int:test_id>/delete_question/<int:question_id>', methods=['POST'])
@login_required
def delete_question(test_id, question_id):
    if current_user.get_id().startswith('student_'):
        flash('Access Denied.', 'danger')
        return redirect(url_for('main.index'))
        
    question = Question.query.filter_by(online_test_id=test_id, id=question_id).first_or_404()
    db.session.delete(question)
    db.session.commit()
    flash('Question deleted successfully.', 'success')
    return redirect(url_for('main.edit_online_test_questions', test_id=test_id))


@main.route('/online_tests/<int:test_id>/assign', methods=['GET', 'POST'])
@login_required
def assign_online_test(test_id):
    if current_user.get_id().startswith('student_'):
        flash('Access Denied.', 'danger')
        return redirect(url_for('main.index'))
        
    test = OnlineTest.query.get_or_404(test_id)

    if request.method == 'POST':
        # Get list of student IDs to assign
        selected_student_ids = [int(sid) for sid in request.form.getlist('student_ids')]
        
        # Remove any existing assignments that are not in the new selection
        existing_assignments = TestAssignment.query.filter_by(online_test_id=test.id).all()
        for ea in existing_assignments:
            if ea.student_id not in selected_student_ids:
                db.session.delete(ea)
            else:
                # remove from our insertion list since it already exists
                selected_student_ids.remove(ea.student_id)

        # Create new assignments
        for sid in selected_student_ids:
            ta = TestAssignment(online_test_id=test.id, student_id=sid)
            db.session.add(ta)
            
        db.session.commit()
        flash(f'Assignments updated for "{test.name}".', 'success')
        return redirect(url_for('main.manage_online_tests'))

    # GET
    students = Student.query.order_by(Student.roll_no).all()
    departments = sorted(set(s.department for s in students if s.department))
    assigned_student_ids = [ta.student_id for ta in TestAssignment.query.filter_by(online_test_id=test.id).all()]

    return render_template('assign_test.html', test=test, students=students, departments=departments, assigned_student_ids=assigned_student_ids)


@main.route('/student/tests')
@login_required
def student_tests():
    if not (isinstance(current_user, Student) or current_user.get_id().startswith('student_')):
        flash('Access Denied: Faculty/Admin cannot view student test page.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    assignments = TestAssignment.query.filter_by(student_id=current_user.id).all()
    return render_template('student_tests.html', assignments=assignments)


@main.route('/student/take_test/<int:assignment_id>')
@login_required
def take_test(assignment_id):
    if not (isinstance(current_user, Student) or current_user.get_id().startswith('student_')):
        flash('Access Denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    assignment = TestAssignment.query.filter_by(id=assignment_id, student_id=current_user.id).first_or_404()
    test = assignment.online_test

    if assignment.is_submitted:
        flash('You have already submitted this test.', 'warning')
        return redirect(url_for('main.student_tests'))

    if not test.start_allowed:
        flash('This test is not currently open for responses.', 'warning')
        return redirect(url_for('main.student_tests'))

    now = datetime.utcnow()
    if not assignment.is_started:
        assignment.is_started = True
        assignment.start_time = now
        db.session.commit()

    elapsed = (now - assignment.start_time).total_seconds()
    duration_seconds = test.duration_minutes * 60
    remaining_seconds = max(0, int(duration_seconds - elapsed))

    if remaining_seconds <= 0:
        return redirect(url_for('main.submit_test', assignment_id=assignment_id))

    max_marks = sum(q.positive_marks for q in test.questions)

    return render_template('take_test.html', 
                           assignment=assignment, 
                           test=test, 
                           remaining_seconds=remaining_seconds, 
                           total_duration_seconds=duration_seconds,
                           max_marks=max_marks)


@main.route('/student/submit_test/<int:assignment_id>', methods=['POST'])
@login_required
def submit_test(assignment_id):
    if not (isinstance(current_user, Student) or current_user.get_id().startswith('student_')):
        return jsonify({'error': 'Unauthorized'}), 403

    assignment = TestAssignment.query.filter_by(id=assignment_id, student_id=current_user.id).first_or_404()
    test = assignment.online_test

    if assignment.is_submitted:
        flash('Test already submitted.', 'warning')
        return redirect(url_for('main.student_tests'))

    now = datetime.utcnow()
    duration_seconds = test.duration_minutes * 60
    elapsed_seconds = (now - assignment.start_time).total_seconds() if assignment.start_time else 0

    StudentResponse.query.filter_by(test_assignment_id=assignment.id).delete()

    score = 0.0
    for q in test.questions:
        selected_opt_ids = [int(oid) for oid in request.form.getlist(f'question_{q.id}_options')]
        
        if elapsed_seconds > duration_seconds + 60:
            selected_opt_ids = [] # Time limit exceeded, ignore their answers

        if elapsed_seconds <= duration_seconds + 60:
            for oid in selected_opt_ids:
                resp = StudentResponse(
                    test_assignment_id=assignment.id,
                    question_id=q.id,
                    option_id=oid
                )
                db.session.add(resp)

        correct_opts = [opt.id for opt in q.options if opt.is_correct]
        
        if not selected_opt_ids:
            question_score = 0.0
        else:
            if set(selected_opt_ids) == set(correct_opts):
                question_score = q.positive_marks
            else:
                question_score = -q.negative_marks
        
        score += question_score

    assignment.score = score
    assignment.is_submitted = True
    assignment.submission_time = now
    
    group_name = f"Online Test: {test.name}"
    assignment_group = AssignmentGroup.query.filter_by(name=group_name, subject=test.subject).first()
    
    total_test_marks = sum(q.positive_marks for q in test.questions)
    
    if not assignment_group:
        assignment_group = AssignmentGroup(
            name=group_name,
            subject=test.subject,
            total_marks=total_test_marks,
            threshold_percent=test.threshold_percent,
            remedial_booked=False
        )
        db.session.add(assignment_group)
        db.session.flush()

    assessment = Assessment(
        student_id=current_user.id,
        subject=test.subject,
        marks=score,
        assignment_group_id=assignment_group.id
    )
    db.session.add(assessment)

    threshold_val = (test.threshold_percent / 100.0) * total_test_marks
    if score < threshold_val:
        learner_type = "Slow Learner"
    else:
        learner_type = "Fast Learner"

    classification = Classification.query.filter_by(
        student_id=current_user.id, subject=test.subject
    ).first()
    if classification:
        classification.learner_type = learner_type
    else:
        classification = Classification(
            student_id=current_user.id,
            subject=test.subject,
            learner_type=learner_type
        )
        db.session.add(classification)

    db.session.commit()
    flash(f'Quiz "{test.name}" submitted successfully! Score: {score} / {total_test_marks}', 'success')
    return redirect(url_for('main.student_tests'))
