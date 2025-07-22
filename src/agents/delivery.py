import os
import re # Make sure 're' is imported at the top
from typing import Optional
from datetime import datetime

from src.config import get_settings
from src.utils import logger
from src.tools.sendgrid_client import sendgrid_client_instance
from src.models.newsletter_models import Newsletter
from src.state import AgentState

settings = get_settings()

def delivery_agent_node(state: AgentState) -> AgentState:
    logger.info("---DELIVERY AGENT: Starting newsletter delivery process---")

    newsletter_draft: Optional[Newsletter] = state.get('newsletter_draft')
    
    new_state = state.copy()
    new_state['newsletter_sent'] = False
    new_state['delivery_report'] = "No action taken."

    if not newsletter_draft or not newsletter_draft.is_approved:
        logger.warning("DELIVERY AGENT: Newsletter not approved or not found. Skipping delivery.")
        new_state['delivery_report'] = "Newsletter not approved or draft missing. Delivery skipped."
        return new_state

    # --- Send Email ---
    recipients = settings.get_newsletter_recipients_list()
    subject = newsletter_draft.subject
    content_html = newsletter_draft.content_html # <--- CHANGED TO content_html

    logger.info(f"DELIVERY AGENT: Attempting to send email to {len(recipients)} recipients.")
    email_sent_successfully = sendgrid_client_instance.send_email(recipients, subject, content_html)

    if email_sent_successfully:
        logger.info("DELIVERY AGENT: Email delivery initiated successfully via SendGrid.")
        new_state['newsletter_sent'] = True
        new_state['delivery_report'] = "Newsletter sent successfully via SendGrid."
        newsletter_draft.sent_timestamp = datetime.now()
    else:
        logger.error("DELIVERY AGENT: Failed to send email via SendGrid. Check logs for details.")
        new_state['delivery_report'] = "Email delivery failed. Check SendGrid logs and API key."
        newsletter_draft.sent_timestamp = None

    # --- Archive Newsletter ---
    try:
        archives_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'archives')
        os.makedirs(archives_dir, exist_ok=True)
        
        safe_subject = re.sub(r'[^\w\s-]', '', subject).strip().replace(' ', '_')
        archive_filename_md = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_subject[:50]}.md"
        archive_filename_html = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_subject[:50]}.html"

        # Archive Markdown version
        archive_path_md = os.path.join(archives_dir, archive_filename_md)
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
        archive_path_html = os.path.join(archives_dir, archive_filename_html)
        with open(archive_path_html, 'w', encoding='utf-8') as f:
            f.write(newsletter_draft.content_html)
        logger.info(f"DELIVERY AGENT: HTML newsletter archived to: {archive_path_html}")

    except Exception as e:
        logger.error(f"DELIVERY AGENT: Error archiving newsletter: {e}", exc_info=True)
        new_state['delivery_report'] += " Archiving failed."

    logger.info("---DELIVERY AGENT: Completed newsletter delivery process---")
    return new_state


# Example usage (for testing purposes)
if __name__ == "__main__":
    print("--- Testing Delivery Agent Node (Standalone) ---")

    # This test will attempt to send a real email if SendGrid is configured correctly.
    # Set NEWSLETTER_RECIPIENTS to your own email in .env for testing!

    # Create a dummy APPROVED newsletter draft for testing
    approved_draft = Newsletter(
        date=datetime.now(),
        subject=f"{settings.NEWSLETTER_SUBJECT_PREFIX} 2025-07-22 Approved Test",
        content_markdown="""## Test Newsletter
This is a **test** newsletter content.
- Item 1
- Item 2
[Link to Docs](https://example.com)
""",
        is_approved=True, # Crucial: set to True for delivery
        approval_score=0.9,
        feedback="Approved.",
        revision_attempts=0
    )

    # Create a dummy NOT APPROVED newsletter draft for testing
    not_approved_draft = Newsletter(
        date=datetime.now(),
        subject=f"{settings.NEWSLETTER_SUBJECT_PREFIX} 2025-07-22 Not Approved Test",
        content_markdown="""## Rejected Newsletter
This content is problematic.
""",
        is_approved=False, # Crucial: set to False for no delivery
        approval_score=0.3,
        feedback="Needs major revision.",
        revision_attempts=1
    )

    # Test Case 1: Approved Draft
    print("\n--- Testing Delivery Agent with APPROVED draft (Expected: Email Sent & Archived) ---")
    initial_state_approved: AgentState = {
        "raw_articles": [],
        "summarized_content": [],
        "newsletter_outline": None,
        "newsletter_draft": approved_draft,
        "revision_needed": False,
        "revision_attempts": 0,
        "newsletter_sent": False, # Initial state
        "delivery_report": None,  # Initial state
    }
    updated_state_approved = delivery_agent_node(initial_state_approved)
    draft_approved_final = updated_state_approved['newsletter_draft']
    print(f"Newsletter Sent (State): {updated_state_approved['newsletter_sent']}")
    print(f"Delivery Report (State): {updated_state_approved['delivery_report']}")
    print(f"Draft Sent Timestamp: {draft_approved_final.sent_timestamp}")
    print(f"Draft Is Approved: {draft_approved_final.is_approved}")


    # Test Case 2: Not Approved Draft
    print("\n--- Testing Delivery Agent with NOT APPROVED draft (Expected: No Email Sent) ---")
    initial_state_not_approved: AgentState = {
        "raw_articles": [],
        "summarized_content": [],
        "newsletter_outline": None,
        "newsletter_draft": not_approved_draft,
        "revision_needed": False,
        "revision_attempts": 0,
        "newsletter_sent": False, # Initial state
        "delivery_report": None,  # Initial state
    }
    updated_state_not_approved = delivery_agent_node(initial_state_not_approved)
    draft_not_approved_final = updated_state_not_approved['newsletter_draft']
    print(f"Newsletter Sent (State): {updated_state_not_approved['newsletter_sent']}")
    print(f"Delivery Report (State): {updated_state_not_approved['delivery_report']}")
    print(f"Draft Sent Timestamp: {draft_not_approved_final.sent_timestamp}")
    print(f"Draft Is Approved: {draft_not_approved_final.is_approved}")