from email.mime.text import MIMEText
import smtplib
import json

def load_email_config():
    try:
        with open('controllers/email_config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("email_config.json not found.")
        return None

    except json.JSONDecodeError as e:
        print(f"Error decoding email_config.json: {e}")
        return None

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_reset_email(to_email, reset_link):
    email_config = load_email_config()
    if not email_config or not all(k in email_config for k in ['smtp_server', 'smtp_port', 'smtp_user', 'smtp_password']):
        raise Exception("Email configuration incomplete or missing.")

    subject = "Password Reset Request"

    html_body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                padding: 20px;
            }}
            .container {{
                max-width: 500px;
                background-color: #ffffff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                text-align: center;
            }}
            .btn {{
                display: inline-block;
                background-color: #007bff;
                color: #ffffff;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
            }}
            .btn:hover {{
                background-color: #0056b3;
            }}
            .footer {{
                margin-top: 20px;
                font-size: 12px;
                color: #666666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Password Reset Request</h2>
            <p>Hi,</p>
            <p>You requested a password reset. Click the button below to reset your password:</p>
            <p><a class="btn" href="{reset_link}" target="_blank">Reset Password</a></p>
            <p>If the button doesn't work, copy and paste the link below into your browser:</p>
            <p><a href="{reset_link}" target="_blank">{reset_link}</a></p>
            <p>This link will expire in 1 hour. If you didn’t request this, you can ignore this email.</p>
            <div class="footer">Thanks, <br> Your App Team</div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = email_config['smtp_user']
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
            server.starttls()  # Secure connection
            server.login(email_config['smtp_user'], email_config['smtp_password'])
            server.sendmail(email_config['smtp_user'], to_email, msg.as_string())

        print(f"Reset email successfully sent to {to_email}")
    except Exception as e:
        print(f"Failed to send reset email to {to_email}: {e}")
