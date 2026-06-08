from flask_mail import Mail, Message
from threading import Thread
from flask import current_app

mail = Mail()

def send_async_email(app, msg):
    with app.app_context():
        try:
            # We wrap this in try-except so the app doesn't crash if email fails
            # In a real system, you'd want proper logging here.
            mail.send(msg)
            print(f"Email sent to {msg.recipients}")
        except Exception as e:
            print(f"Failed to send email: {e}")

def send_remedial_notification(faculty_email, student_name, subject, marks, remedial_date):
    msg = Message('Remedial Class Scheduled',
                  recipients=[faculty_email])
    
    msg.body = f"""
    Hello,

    A remedial class has been scheduled for {student_name} in {subject}.
    The student scored {marks} marks, which is below the threshold.
    
    Remedial Date: {remedial_date.strftime('%Y-%m-%d %H:%M')}
    
    Please prepare accordingly.

    Regards,
    Automated System
    """
    
    app = current_app._get_current_object()
    thread = Thread(target=send_async_email, args=[app, msg])
    thread.start()
