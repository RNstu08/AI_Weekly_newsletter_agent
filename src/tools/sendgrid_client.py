import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email
from src.config import get_settings
from src.utils import logger
from typing import List
from datetime import datetime 

settings = get_settings()

class SendGridClient:
    """
    A client to send emails using SendGrid.
    """
    def __init__(self):
        if not settings.SENDGRID_API_KEY:
            logger.error("SENDGRID_API_KEY not found in environment variables. Email sending will not function.")
            raise ValueError("SENDGRID_API_KEY is required for SendGridClient.")
        self.sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        self.sender_email = settings.NEWSLETTER_SENDER_EMAIL
        logger.info(f"SendGridClient initialized with sender email: {self.sender_email}")

    def send_email(self, recipients: List[str], subject: str, content_html: str) -> bool:
        """
        Sends an email to the specified recipients.
        Args:
            recipients (List[str]): List of recipient email addresses.
            subject (str): The subject of the email.
            content_html (str): The HTML content of the email body.
        Returns:
            bool: True if email was sent successfully, False otherwise.
        """
        if not recipients:
            logger.warning("No recipients provided for email. Skipping send.")
            return False

        logger.info(f"Attempting to send email to {len(recipients)} recipients with subject: '{subject}'")

        message = Mail(
            from_email=self.sender_email,
            to_emails=recipients,
            subject=subject,
            html_content=content_html
        )
        try:
            response = self.sg.send(message)
            if response.status_code in [200, 202]:
                logger.info(f"Email sent successfully! Status Code: {response.status_code}")
                return True
            else:
                logger.error(f"Failed to send email. Status Code: {response.status_code}, Body: {response.body}, Headers: {response.headers}")
                return False
        except Exception as e:
            logger.error(f"Error sending email via SendGrid: {e}", exc_info=True)
            return False

# Instantiate the client
sendgrid_client_instance = SendGridClient()

# Example usage (for testing purposes)
if __name__ == "__main__":
    # Ensure SENDGRID_API_KEY, NEWSLETTER_SENDER_EMAIL, NEWSLETTER_RECIPIENTS are set in .env
    # For testing, ensure NEWSLETTER_RECIPIENTS contains YOUR OWN EMAIL ADDRESS
    # as SendGrid often restricts sending to unverified recipients in free/dev tiers.
    
    test_recipients = settings.get_newsletter_recipients_list()
    test_subject = "Test AI Agent Newsletter - Phase 3 Step 1"
    test_html_content = """
    <html>
    <body>
        <h1>Hello from AI Agent!</h1>
        <p>This is a test email sent from the SendGrid client wrapper.</p>
        <p>If you received this, the SendGrid integration is working!</p>
        <p>Current Time: {}</p>
    </body>
    </html>
    """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    if not test_recipients:
        print("No recipients configured in .env for testing (NEWSLETTER_RECIPIENTS). Please set it to your email.")
    else:
        print(f"Attempting to send test email to: {test_recipients}")
        success = sendgrid_client_instance.send_email(test_recipients, test_subject, test_html_content)
        if success:
            print("Test email send initiated. Check your inbox.")
        else:
            print("Test email send failed. Check logs for details.")