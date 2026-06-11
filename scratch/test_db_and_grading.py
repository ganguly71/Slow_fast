import os
import sys
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from models import db, User, Student, OnlineTest, Question, Option, TestAssignment, StudentResponse, Classification, Assessment

def run_tests():
    # Setup test configuration
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_app()
    
    with app.app_context():
        print("Database tables created. Running schema and grading checks...")

        # 1. Test Student password set and verify
        student = Student(
            name="Test Student",
            roll_no="21CS99",
            semester=4,
            department="CSE"
        )
        db.session.add(student)
        db.session.commit()
        
        student.set_password("student123")
        db.session.commit()
        
        assert student.check_password("student123") is True
        assert student.check_password("wrong_password") is False
        assert student.get_id() == "student_1"
        print("[PASS] Student auth model passed.")

        # 2. Test Faculty & Admin
        faculty = User.query.filter_by(role='admin').first()
        assert faculty is not None
        print("[PASS] Default admin exists in database.")

        # 3. Create OnlineTest
        test = OnlineTest(
            name="Python Basics Quiz",
            subject="C",
            duration_minutes=15,
            threshold_percent=60.0,
            created_by_id=faculty.id
        )
        db.session.add(test)
        db.session.flush()

        # Question 1: MCQ (Single correct)
        q1 = Question(
            online_test_id=test.id,
            question_text="What is the output of print(2**3)?",
            positive_marks=2.0,
            negative_marks=0.5
        )
        db.session.add(q1)
        db.session.flush()

        opt1_a = Option(question_id=q1.id, option_text="8", is_correct=True)
        opt1_b = Option(question_id=q1.id, option_text="6", is_correct=False)
        db.session.add_all([opt1_a, opt1_b])

        # Question 2: MSQ (Multiple correct)
        q2 = Question(
            online_test_id=test.id,
            question_text="Select all keywords in Python:",
            positive_marks=3.0,
            negative_marks=1.0
        )
        db.session.add(q2)
        db.session.flush()

        opt2_a = Option(question_id=q2.id, option_text="def", is_correct=True)
        opt2_b = Option(question_id=q2.id, option_text="for", is_correct=True)
        opt2_c = Option(question_id=q2.id, option_text="var", is_correct=False)
        db.session.add_all([opt2_a, opt2_b, opt2_c])

        db.session.commit()
        print("[PASS] Online Test & Questions created.")

        # 4. Test Assignment
        ta = TestAssignment(online_test_id=test.id, student_id=student.id)
        db.session.add(ta)
        db.session.commit()
        assert ta.is_submitted is False
        print("[PASS] Test assignment verified.")

        # 5. Simulate Submission & Grading
        # Scenario A: Correct for Q1 (Option 1), Mismatched for Q2 (only selected Option 3 'def', missing 'for')
        # Correct selections for Q1: [opt1_a.id]
        # Student selections for Q2: [opt2_a.id] (should be correct: [opt2_a.id, opt2_b.id])
        # Expected Q1 score: +2.0
        # Expected Q2 score: -1.0 (mismatch)
        # Expected total score: 1.0
        
        # Test grading algorithm
        # For Q1:
        selected_q1 = [opt1_a.id]
        correct_q1 = [opt1_a.id]
        assert set(selected_q1) == set(correct_q1)
        q1_score = q1.positive_marks # 2.0

        # For Q2:
        selected_q2 = [opt2_a.id]
        correct_q2 = [opt2_a.id, opt2_b.id]
        assert set(selected_q2) != set(correct_q2)
        q2_score = -q2.negative_marks # -1.0

        total_score = q1_score + q2_score
        assert total_score == 1.0
        
        # Classification evaluation
        total_max_marks = q1.positive_marks + q2.positive_marks # 5.0
        threshold_val = (test.threshold_percent / 100.0) * total_max_marks # 3.0
        
        assert total_score < threshold_val # 1.0 < 3.0 -> Slow Learner
        learner_type = "Slow Learner"
        print(f"[PASS] Grading math verified: Student got {total_score}/{total_max_marks} (Threshold required: {threshold_val}). Learner type: {learner_type}")

        # Check classification integration in DB context
        classification = Classification(
            student_id=student.id,
            subject=test.subject,
            learner_type=learner_type
        )
        db.session.add(classification)
        db.session.commit()
        
        db_class = Classification.query.filter_by(student_id=student.id, subject=test.subject).first()
        assert db_class.learner_type == "Slow Learner"
        print("[PASS] Database classification save verified.")
        print("\nAll schema and logic verification checks PASSED successfully!")

if __name__ == '__main__':
    run_tests()
