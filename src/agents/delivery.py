import os
import re
from typing import Optional, List
from datetime import datetime
import markdown
import premailer

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email

from src.config import get_settings
# Import DATA_DIR along with other utilities
from src.utils import logger, load_state_from_json, save_state_to_json, DATA_DIR 
from src.models.newsletter_models import Newsletter
from src.state import AgentState 

settings = get_settings()

# Instantiate SendGridClient globally for efficiency.
class SendGridClientWrapper:
    """
    A client to send emails using SendGrid.
    """
    def __init__(self):
        if not settings.SENDGRID_API_KEY:
            logger.error("SENDGRID_API_KEY not found in environment variables. Email sending will not function.")
            raise ValueError("SENDGRID_API_KEY is required for SendGridClientWrapper.")
        self.sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        self.sender_email = settings.NEWSLETTER_SENDER_EMAIL
        logger.info(f"SendGridClientWrapper initialized with sender email: {self.sender_email}")

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

sendgrid_client_instance = SendGridClientWrapper()


def delivery_agent_node(state: AgentState) -> AgentState:
    """
    Delivery Agent node: Handles the final delivery of the newsletter and archives it.
    - Checks if the newsletter draft is approved.
    - Inlines CSS for email compatibility using premailer.
    - Sends the email using SendGrid.
    - Archives the Markdown and HTML versions of the sent/attempted newsletter.
    - Updates 'newsletter_sent' and 'delivery_report' in the state.
    """
    logger.info("---DELIVERY AGENT: Starting newsletter delivery process---")

    newsletter_draft: Optional[Newsletter] = state.get('newsletter_draft')

    new_state = state.copy()
    new_state['newsletter_sent'] = False
    new_state['delivery_report'] = "No action taken."

    if not newsletter_draft or not newsletter_draft.is_approved:
        logger.warning("DELIVERY AGENT: Newsletter not approved or not found. Skipping delivery.")
        new_state['delivery_report'] = "Newsletter not approved or draft missing. Delivery skipped."
        return new_state

    # --- CSS Inlining (HTML is already templated in Generation Agent) ---
    final_html_to_send = ""
    try:
        if newsletter_draft.content_html:
            # Apply Premailer for CSS Inlining. The content_html already includes the full template.
            final_html_to_send = premailer.transform(newsletter_draft.content_html)
            logger.info("DELIVERY AGENT: CSS inlined successfully using Premailer.")
        else:
            logger.warning("DELIVERY AGENT: No HTML content found in draft. Using markdown content as fallback HTML.")
            # This fallback should ideally not be hit if Generation Agent works correctly
            final_html_to_send = markdown.markdown(newsletter_draft.content_markdown) # Fallback

    except Exception as e:
        logger.error(f"DELIVERY AGENT: Error preparing HTML for delivery (Premailer): {e}", exc_info=True)
        final_html_to_send = markdown.markdown(newsletter_draft.content_markdown) # Fallback to raw markdown HTML


    # --- Send Email ---
    recipients: List[str] = state.get('recipients', settings.get_newsletter_recipients_list())
    if not recipients:
        logger.error("DELIVERY AGENT: No recipients found in state or settings. Cannot send email.")
        new_state['delivery_report'] = "No recipients configured. Delivery skipped."
        return new_state

    subject = newsletter_draft.subject
    content_to_send = final_html_to_send # Use the fully processed HTML

    logger.info(f"DELIVERY AGENT: Attempting to send newsletter to {len(recipients)} recipients.")
    email_sent_successfully = sendgrid_client_instance.send_email(recipients, subject, content_to_send)

    if email_sent_successfully:
        logger.info("DELIVERY AGENT: Email delivery initiated successfully via SendGrid.")
        new_state['newsletter_sent'] = True
        new_state['delivery_report'] = "Newsletter sent successfully via SendGrid."
        newsletter_draft.sent_timestamp = datetime.now()
        # Update content_html on the draft object with the final inlined HTML for archiving
        newsletter_draft.content_html = final_html_to_send
    else:
        logger.error("DELIVERY AGENT: Failed to send email via SendGrid. Check logs for details.")
        new_state['delivery_report'] = "Email delivery failed. Check SendGrid logs and API key."
        newsletter_draft.sent_timestamp = None
        newsletter_draft.content_html = final_html_to_send # Still save it for debugging even if send failed


    # --- Archive Newsletter ---
    try:
        # Use DATA_DIR imported from utils
        archives_dir = DATA_DIR / 'archives' 
        os.makedirs(archives_dir, exist_ok=True)

        safe_subject = re.sub(r'[^\w\s-]', '', subject).strip().replace(' ', '_')
        archive_filename_md = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_subject[:50]}.md"
        archive_filename_html = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_subject[:50]}.html"

        # Archive Markdown version
        archive_path_md = archives_dir / archive_filename_md
        with open(archive_path_md, 'w', encoding='utf-8') as f:
            f.write(f"Subject: {newsletter_draft.subject}\n\n")
            f.write(f"Date: {newsletter_draft.date.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Approval Score: {newsletter_draft.approval_score:.2f}\n")
            f.write(f"Feedback: {newsletter_draft.feedback}\n")
            f.write(f"Revision Attempts: {newsletter_draft.revision_attempts}\n")
            f.write(f"Sent Timestamp: {newsletter_draft.sent_timestamp.strftime('%Y-%m-%d %H:%M:%S') if newsletter_draft.sent_timestamp else 'N/A'}\n\n")
            f.write("---\n\n")
            f.write(newsletter_draft.content_markdown)
        logger.info(f"DELIVERY AGENT: Markdown newsletter archived to: {archive_path_md}")

        # Archive HTML version
        archive_path_html = archives_dir / archive_filename_html
        with open(archive_path_html, 'w', encoding='utf-8') as f:
            f.write(newsletter_draft.content_html if newsletter_draft.content_html else "")
        logger.info(f"DELIVERY AGENT: HTML newsletter archived to: {archive_path_html}")

    except Exception as e:
        logger.error(f"DELIVERY AGENT: Error archiving newsletter: {e}", exc_info=True)
        new_state['delivery_report'] += " Archiving failed."

    logger.info("---DELIVERY AGENT: Completed newsletter delivery process---")
    return new_state

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("--- Testing Delivery Agent Node (Standalone) ---")

    # Ensure DATA_DIR, load_state_from_json, save_state_to_json are imported for this __main__ block
    # These imports are already at the top of the file but need to be explicitly used here
    # No need to re-import, just ensure they are available to this scope.
    
    # Try loading final_newsletter_draft from file
    loaded_draft_data = load_state_from_json("final_newsletter_draft_state.json", DATA_DIR).get('newsletter_draft', None)
    loaded_newsletter_draft = None
    if loaded_draft_data:
        # Reconstruct Newsletter object. Be careful with datetime if not isoformat.
        loaded_draft_data['date'] = datetime.fromisoformat(loaded_draft_data['date'])
        if loaded_draft_data.get('sent_timestamp'): # Use .get safely
            loaded_draft_data['sent_timestamp'] = datetime.fromisoformat(loaded_draft_data['sent_timestamp'])
        loaded_newsletter_draft = Newsletter(**loaded_draft_data) # Reconstruct Newsletter object
        print("Loaded newsletter draft from file.")
    else:
        print("\nWARNING: No final_newsletter_draft_state.json found or it's empty. Cannot test delivery properly.")
        # Create a dummy APPROVED newsletter draft for testing if file doesn't exist or is empty
        current_date_header = datetime.now().strftime('%B %d, %Y')
        current_year = datetime.now().year
        test_subject = f"{settings.NEWSLETTER_SUBJECT_PREFIX} {datetime.now().strftime('%Y-%m-%d')} APPROVED Test"
        dummy_full_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{test_subject}</title>
            <style type="text/css"> /* Explicit type for email compatibility */
                body {{ font-family: sans-serif; background-color: #f4f4f4; }}
                .header-section {{ background-color: #2980b9; color: #ffffff; padding: 20px; text-align: center; }}
                .container {{ max-width: 700px; margin: 20px auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                h2 {{ color: #34495e; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
                a {{ color: #3498db; text-decoration: none; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 0.8em; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <div class="header-section">
                <h1>The AI Agent Weekly Digest</h1>
                <p class="date-info">{current_date_header}</p>
            </div>
            <div class="container">
                <h2>Introduction</h2>
                <p>This is a <strong>test</strong> newsletter content designed to check styling and delivery.</p>
                <p>This is a second line of the introduction.</p>
                <p>This is a third line, making sure the length requirement is met.</p>

                <h2>Featured Articles</h2>
                <h3><a href="https://example.com/article1">Example Article 1 Title</a></h3>
                <ul>
                    <li>Summary: This is a summary of the first example article for testing purposes.</li>
                </ul>
                <a href="https://example.com/article1" class="read-more-link">Read More</a>
                
                <h2>Conclusion</h2>
                <p>This is a test conclusion with 2-3 lines of text. It summarizes well.</p>
                <p>Hope you found this digest informative.</p>

                <p><strong>Overall Trends:</strong></p>
                <ul>
                    <li>- Trend 1</li>
                    <li>- Trend 2</li>
                </ul>
            </div>
            <div class="footer">
                <p>This newsletter is generated by an AI Agent. | &copy; {current_year} AI Agent News</p>
                <p>Stay updated on the latest in AI Agent Development!</p>
            </div>
        </body>
        </html>
        """

        approved_draft = Newsletter(
            date=datetime.now(),
            subject=test_subject,
            content_markdown="This is markdown content (won't be used directly by delivery anymore)",
            content_html=dummy_full_html, # Now contains the full HTML with template
            is_approved=True, # Mark as approved for testing delivery
            approval_score=0.9,
            feedback="Approved for delivery (dummy).",
            revision_attempts=0
        )
        loaded_newsletter_draft = approved_draft

    # Initial state for Delivery Agent
    initial_state: AgentState = {
        "raw_articles": [], "summarized_content": [], "newsletter_outline": None,
        "newsletter_draft": loaded_newsletter_draft, 
        "revision_needed": False, "revision_attempts": 0,
        "newsletter_sent": False, "delivery_report": None,
        "recipients": settings.get_newsletter_recipients_list()
    }

    # Run the delivery agent node
    updated_state = delivery_agent_node(initial_state)
    draft_final = updated_state['newsletter_draft']

    print(f"\n--- Delivery Agent Results ---")
    print(f"Newsletter Sent (State): {updated_state['newsletter_sent']}")
    print(f"Delivery Report (State): {updated_state['delivery_report']}")
    print(f"Draft Sent Timestamp: {draft_final.sent_timestamp}")
    print(f"Draft Is Approved: {draft_final.is_approved}")

    if updated_state['newsletter_sent']:
        print("\nEmail delivery successful! Check your inbox.")
    else:
        print("\nEmail delivery failed or skipped. Check logs for details.")