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



