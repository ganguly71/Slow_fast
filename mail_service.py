import os
import requests
from threading import Thread
from flask import current_app

def send_async_email(app, payload, headers):
    with app.app_context():
        try:
            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                json=payload,
                headers=headers,
                timeout=10
            )
            if response.status_code in [200, 201, 202]:
                print(f"[Mail Service] Email sent successfully! Response: {response.text}")
            else:
                print(f"[Mail Service] Failed to send email via Brevo. Code: {response.status_code}, Response: {response.text}")
        except Exception as e:
            print(f"[Mail Service] Error sending email via Brevo: {e}")

def send_remedial_notification(faculty_email, student_name, subject, marks, remedial_date):
    api_key = os.environ.get('BREVO_API_KEY')
    if not api_key:
        print("[Mail Service] ERROR: BREVO_API_KEY environment variable is not set!")
        return

    sender_email = os.environ.get('SENDER_EMAIL', 'adityava49cse@gmail.com')

    # Prepare Brevo API payload
    payload = {
        "sender": {
            "name": "Academics System",
            "email": sender_email
        },
        "to": [
            {
                "email": faculty_email
            }
        ],
        "subject": "Remedial Class Scheduled",
        "htmlContent": f"""
        <p>Hello,</p>
        <p>A remedial class has been scheduled for <strong>{student_name}</strong> in <strong>{subject}</strong>.</p>
        <p>The student scored <strong>{marks}</strong> marks, which is below the threshold.</p>
        <p><strong>Remedial Date:</strong> {remedial_date.strftime('%Y-%m-%d %H:%M')}</p>
        <p>Please prepare accordingly.</p>
        <p>Regards,<br>Automated System</p>
        """
    }

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    app = current_app._get_current_object()
    thread = Thread(target=send_async_email, args=[app, payload, headers])
    thread.start()


def send_remedial_batch_notification(faculty_email, assignment_name, subject, student_list, remedial_date):
    """Send a single consolidated email to the faculty with the full list of
    slow-learner students (name + roll number) who will attend the remedial.

    Args:
        faculty_email: email address of the assigned faculty
        assignment_name: name of the assignment (e.g. "Mid-Sem 1")
        subject: subject code (e.g. "COA")
        student_list: list of dicts with keys 'name', 'roll_no', 'marks'
        remedial_date: datetime of the scheduled remedial class
    """
    api_key = os.environ.get('BREVO_API_KEY')
    if not api_key:
        print("[Mail Service] ERROR: BREVO_API_KEY environment variable is not set!")
        return

    sender_email = os.environ.get('SENDER_EMAIL', 'adityava49cse@gmail.com')

    # Build the student table rows
    student_rows = ""
    for idx, s in enumerate(student_list, 1):
        student_rows += f"""
        <tr>
            <td style="padding:8px; border:1px solid #ddd; text-align:center;">{idx}</td>
            <td style="padding:8px; border:1px solid #ddd;">{s['roll_no']}</td>
            <td style="padding:8px; border:1px solid #ddd;">{s['name']}</td>
            <td style="padding:8px; border:1px solid #ddd; text-align:center;">{s['marks']}</td>
        </tr>"""

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
        <h2 style="color: #2c3e50;">Remedial Class Scheduled</h2>
        <p>Hello,</p>
        <p>A remedial class has been booked for the assignment <strong>{assignment_name}</strong>
           in <strong>{subject}</strong>.</p>
        <p><strong>Remedial Date:</strong> {remedial_date.strftime('%Y-%m-%d %H:%M')}</p>
        <p>The following <strong>{len(student_list)}</strong> student(s) scored below the threshold
           and are expected to attend:</p>

        <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
            <thead>
                <tr style="background-color: #3498db; color: white;">
                    <th style="padding:8px; border:1px solid #ddd;">#</th>
                    <th style="padding:8px; border:1px solid #ddd;">Roll No</th>
                    <th style="padding:8px; border:1px solid #ddd;">Student Name</th>
                    <th style="padding:8px; border:1px solid #ddd;">Marks</th>
                </tr>
            </thead>
            <tbody>
                {student_rows}
            </tbody>
        </table>

        <p>Please prepare accordingly.</p>
        <p>Regards,<br>Automated Academics System</p>
    </div>
    """

    payload = {
        "sender": {
            "name": "Academics System",
            "email": sender_email
        },
        "to": [
            {
                "email": faculty_email
            }
        ],
        "subject": f"Remedial Class — {assignment_name} ({subject})",
        "htmlContent": html_content
    }

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    app = current_app._get_current_object()
    thread = Thread(target=send_async_email, args=[app, payload, headers])
    thread.start()
