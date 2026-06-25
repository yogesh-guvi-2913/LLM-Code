import smtplib, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from app.config import SMTP_USERNAME, SMTP_PASSWORD, SMTP_SERVER, SMTP_SENDER_EMAIL

logger = logging.getLogger(__name__)

def send_email(subject, body, to_email, reply_to_email = 'research@guvi.in', from_name = 'GUVI Research', cc_emails = None):
    from_email = SMTP_SENDER_EMAIL
    smtp_username = SMTP_USERNAME
    smtp_password = SMTP_PASSWORD
    smtp_server = SMTP_SERVER
    smtp_port = 465 

    # Create message container
    msg = MIMEMultipart()
    msg['From'] = formataddr((from_name, from_email))
    msg['From'] = from_email
    msg['To'] = ', '.join(to_email) if isinstance(to_email, list) else to_email
    msg['Subject'] = subject
    msg['Reply-To'] = reply_to_email

    # Add CC if provided and join list
    if cc_emails:
        msg['Cc'] = ', '.join(cc_emails) if isinstance(cc_emails, list) else cc_emails

    # Attach the body with the msg instance
    msg.attach(MIMEText(body, 'html'))

    # Setup the server
    server = smtplib.SMTP_SSL(smtp_server, smtp_port)

    # Login credentials for sending the mail
    server.login(smtp_username, smtp_password)

    # Send the email
    text = msg.as_string()
    response = server.sendmail(from_email, to_email, text)
    logger.info(f"Email sent successfully to {to_email} with response: {response}")

    # Disconnect from the server
    server.quit()

class EmailTemplates():

    def acceptance(data):
        template=f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Hackathon Progress Notification</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: #f4f4f4;
                        margin: 0;
                        padding: 0;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 50px auto;
                        background-color: #ffffff;
                        padding: 20px;
                        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                        border-radius: 8px;
                    }}
                    .header {{
                        background-color: #007bff;
                        color: #ffffff;
                        padding: 10px 0;
                        text-align: center;
                        border-radius: 8px 8px 0 0;
                    }}
                    .content {{
                        padding: 20px;
                    }}
                    .content h2 {{
                        color: #333333;
                    }}
                    .content p {{
                        color: #555555;
                    }}
                    .footer {{
                        text-align: center;
                        padding: 10px 0;
                        color: #888888;
                        font-size: 12px;
                    }}
                    .button {{
                        display: inline-block;
                        color: #FFFFFF !important;
                        background-color: #0056b3;
                        padding: 10px 20px;
                        text-decoration: none;
                        border-radius: 5px;
                        margin-top: 20px;
                    }}
                    .button:hover {{
                        color: #FFFFFF;
                        background-color: #0056b5;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>{data['hackathonTitle']}</h1>
                    </div>
                    <div class="content">
                        <h2>Congratulations, {data['userName']}!</h2>
                        <p>We are thrilled to inform you that you have successfully advanced from <strong>{data['fromLevel']}</strong> to <strong>{data['toLevel']}</strong> in the <strong>{data['hackathonTitle']}</strong>.</p>
                        <p>Your dedication and hard work have truly paid off, and we are excited to see what you accomplish in the next stage.</p>
                        <p>Keep pushing your limits and continue to innovate. The journey is just getting started!</p>
                        <a href="{data['dashboardUrl']}" class="button">View Dashboard</a>
                    </div>
                    <div class="footer">
                        <p>© 2024 {data['hackathonTitle']}. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
        """

        return template
