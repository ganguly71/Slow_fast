import os
import resend
from threading import Thread
from flask import current_app

def send_async_email(app, params):
    with app.app_context():
        api_key = os.environ.get('RESEND_API_KEY')
        if not api_key:
            print("[Mail Service] ERROR: RESEND_API_KEY environment variable is not set!")
            return
            
        try:
            resend.api_key = api_key
            email = resend.Emails.send(params)
            print(f"[Mail Service] Email sent successfully! Response: {email}")
        except Exception as e:
            print(f"[Mail Service] Failed to send email via Resend: {e}")
            print("[Mail Service] Troubleshooting Tip: If you are using Resend's free/sandbox tier, make sure the recipient email is the one you signed up with.")

def send_remedial_notification(faculty_email, student_name, subject, marks, remedial_date):
    # Support overriding the recipient email for Resend sandbox mode
    to_email = os.environ.get('RESEND_TO_EMAIL')
    if to_email:
        recipient = to_email
        print(f"[Mail Service] Overriding recipient to Resend verified email: {recipient}")
    else:
        recipient = faculty_email

    params = {
        "from": "Academics <onboarding@resend.dev>",
        "to": [recipient],
        "subject": "Remedial Class Scheduled",
        "html": f"""
        <p>Hello,</p>
        <p>A remedial class has been scheduled for <strong>{student_name}</strong> in <strong>{subject}</strong>.</p>
        <p>The student scored <strong>{marks}</strong> marks, which is below the threshold.</p>
        <p><strong>Remedial Date:</strong> {remedial_date.strftime('%Y-%m-%d %H:%M')}</p>
        <p>Please prepare accordingly.</p>
        <p>Regards,<br>Automated System</p>
        """
    }
    
    app = current_app._get_current_object()
    thread = Thread(target=send_async_email, args=[app, params])
    thread.start()


