import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import get_settings
from src.utils import logger, clean_json_string, load_state_from_json, save_state_to_json, DATA_DIR, escape_quotes_in_json_string_values 
from src.tools.llm_interface import get_default_llm # Our LLM interface
from src.models.newsletter_models import Newsletter 
from src.models.research_models import SummarizedContent # To pass original summarized content for factual check
from src.prompts.editorial_prompts import EDITORIAL_REVIEW_PROMPT
from src.state import AgentState # Our shared state definition

# Load application settings
settings = get_settings()

# Initialize the LLM for this agent
editorial_llm = get_default_llm()

def editorial_agent_node(state: AgentState) -> AgentState:
    """
    Editorial Agent node: Reviews the generated newsletter draft for quality,
    factual accuracy, and adherence to guidelines.
    - Uses an LLM (as a 'judge') to score the newsletter and provide feedback.
    - Determines if the newsletter needs revision based on the quality score and revision attempts.
    - Updates 'newsletter_draft', 'is_approved', 'feedback', 'revision_needed', 'revision_attempts' in the state.
    """
    logger.info("---EDITORIAL AGENT: Starting newsletter review---")

    newsletter_draft: Optional[Newsletter] = state.get('newsletter_draft')
    summarized_content: List[SummarizedContent] = state.get('summarized_content', [])
    revision_attempts: int = state.get('revision_attempts', 0)

    if not newsletter_draft:
        logger.error("EDITORIAL AGENT: No newsletter draft found in state. Cannot perform review.")
        new_state = state.copy()
        new_state['newsletter_draft'] = Newsletter(
            date=datetime.now(),
            subject="ERROR: No Draft Available",
            content_markdown="No newsletter draft was available for review due to a prior error.",
            is_approved=False,
            approval_score=0.0,
            feedback="No newsletter draft available for review.",
            revision_attempts=revision_attempts
        )
        new_state['revision_needed'] = False # Can't revise if no draft
        return new_state
    
    # Prepare summarized content for LLM's factual verification
    summarized_articles_json_str = json.dumps([
        sa.model_dump() for sa in summarized_content
    ], indent=2)

    try:
        logger.info(f"EDITORIAL AGENT: Invoking LLM to review newsletter draft (Attempt {revision_attempts + 1}).")
        # Ensure the prompt is correctly formatted for the LLM
        prompt_messages = EDITORIAL_REVIEW_PROMPT.format_messages(
            subject=newsletter_draft.subject,
            content_markdown=newsletter_draft.content_markdown,
            summarized_articles_json=summarized_articles_json_str
        )
        response_content = editorial_llm.invoke(prompt_messages) # Invoke with formatted messages

        # Safely extract content from LLM response (handle both BaseMessage and str)
        llm_raw_output_str = response_content.content if hasattr(response_content, 'content') else str(response_content)


        parsed_llm_output = {}
        original_response_for_retry = llm_raw_output_str # Keep a copy for retry attempts
        
        try_count = 0
        max_tries = 3

        while try_count < max_tries:
            try:
                # Use the robust clean_json_string from utils for first pass
                cleaned_json_str = clean_json_string(original_response_for_retry)
                
                # Assert for debugging: ensures the cleaned string actually looks like JSON
                assert cleaned_json_str.startswith('{') and cleaned_json_str.endswith('}'), \
                    f"Cleaned JSON string does not start/end with braces for scoring: {cleaned_json_str[:100]}..."

                parsed_llm_output = json.loads(cleaned_json_str)
                break # Parsing successful, break loop
            except (json.JSONDecodeError, ValueError) as e: # Catch both JSON parsing and ValueError from clean_json_string
                logger.warning(f"EDITORIAL AGENT: JSONDecodeError/ValueError for editorial review on try {try_count+1}: {e}. Raw response (cleaned, first 500 chars): '{cleaned_json_str[:500]}...'")
                
                if try_count < max_tries - 1: # Only apply retry fix if there's at least one more try
                    # Apply a targeted escape for problematic internal quotes and retry
                    original_response_for_retry = escape_quotes_in_json_string_values(original_response_for_retry)
                    logger.warning(f"EDITORIAL AGENT: Attempting inner quote escape and retry for editorial review.")
                
                try_count += 1
                if try_count == max_tries:
                    logger.error(f"EDITORIAL AGENT: Max retries reached for JSON parsing for editorial review. Setting score to 0.0.")
                    raise # Re-raise after max tries to trigger the outer except

        quality_score = float(parsed_llm_output.get('quality_score', 0.0))
        # We ignore LLM's direct 'is_approved' flag here and rely solely on our threshold logic
        feedback_from_llm = parsed_llm_output.get('feedback', 'No specific feedback provided.')
        issues_found = parsed_llm_output.get('issues_found', [])
        
        logger.info(f"EDITORIAL AGENT: LLM review complete. Score: {quality_score:.2f}.")
        
        # --- Determine final approval status based on score and attempts ---
        final_is_approved = False
        revision_needed = False
        overall_feedback = feedback_from_llm # Start with LLM's feedback

        if quality_score >= settings.EDITORIAL_MIN_QUALITY_SCORE:
            final_is_approved = True
            logger.info("EDITORIAL AGENT: Newsletter approved based on quality score threshold.")
            overall_feedback = "Approved."
        else:
            logger.warning(f"EDITORIAL AGENT: Newsletter score ({quality_score:.2f}) below threshold ({settings.EDITORIAL_MIN_QUALITY_SCORE}).")
            
            if revision_attempts < settings.EDITORIAL_MAX_REVISION_ATTEMPTS:
                revision_needed = True
                logger.info(f"EDITORIAL AGENT: Revision needed. Attempt {revision_attempts + 1}/{settings.EDITORIAL_MAX_REVISION_ATTEMPTS}.")
                overall_feedback = f"Revision requested (Attempt {revision_attempts + 1}): {overall_feedback}"
                # Add specific issues to feedback if available
                if issues_found:
                    issue_descriptions = [f"- {issue.get('type', 'Unknown Type')}: {issue.get('description', 'No description')}" for issue in issues_found]
                    overall_feedback += "\n\nIssues Found:\n" + "\n".join(issue_descriptions)
            else:
                logger.error(f"EDITORIAL AGENT: Max revision attempts ({settings.EDITORIAL_MAX_REVISION_ATTEMPTS}) reached. Newsletter NOT approved.")
                final_is_approved = False
                revision_needed = False
                overall_feedback = f"Max revision attempts reached. Newsletter NOT approved. Final Feedback: {overall_feedback}"
                if issues_found:
                    issue_descriptions = [f"- {issue.get('type', 'Unknown Type')}: {issue.get('description', 'No description')}" for issue in issues_found]
                    overall_feedback += "\n\nFinal Issues:\n" + "\n".join(issue_descriptions)

        # Update the newsletter draft object and state
        newsletter_draft.is_approved = final_is_approved
        newsletter_draft.approval_score = quality_score
        newsletter_draft.feedback = overall_feedback
        # Only increment revision_attempts if revision is indeed needed (or if LLM parsing failed)
        newsletter_draft.revision_attempts = revision_attempts + 1 if revision_needed or (quality_score == 0.0 and "Failed to parse" in overall_feedback) else revision_attempts

    except Exception as e:
        logger.error(f"EDITORIAL AGENT: Critical error during LLM review process for '{newsletter_draft.subject}': {e}", exc_info=True)
        # This catch-all handles any unexpected errors during LLM invocation or primary parsing logic
        newsletter_draft.is_approved = False
        newsletter_draft.approval_score = 0.0
        newsletter_draft.feedback = "Critical internal error during editorial review. Manual intervention required."
        newsletter_draft.revision_attempts = revision_attempts + 1 # Still count this as an attempt
        revision_needed = True if revision_attempts < settings.EDITORIAL_MAX_REVISION_ATTEMPTS else False # Attempt revision if not maxed out

    logger.info("---EDITORIAL AGENT: Completed newsletter review---")

    # Update the state with the modified newsletter draft and revision flags
    new_state = state.copy()
    new_state['newsletter_draft'] = newsletter_draft
    new_state['revision_needed'] = revision_needed
    new_state['revision_attempts'] = newsletter_draft.revision_attempts # Ensure this is updated for graph routing
    return new_state

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("--- Testing Editorial Agent Node (Standalone) ---")

    # Import DATA_DIR, load_state_from_json, save_state_to_json for this __main__ block
    # These imports are already at the top of the file but need to be explicitly used here
    # No need to re-import, just ensure they are available to this scope.

    # Try loading newsletter_draft from file
    loaded_draft_data = load_state_from_json("newsletter_draft_state.json", DATA_DIR).get('newsletter_draft', None)
    loaded_newsletter_draft = None
    if loaded_draft_data:
        # Reconstruct Newsletter object. Be careful with datetime if not isoformat.
        loaded_draft_data['date'] = datetime.fromisoformat(loaded_draft_data['date'])
        if loaded_draft_data.get('sent_timestamp'): # Use .get safely
            loaded_draft_data['sent_timestamp'] = datetime.fromisoformat(loaded_draft_data['sent_timestamp'])
        loaded_newsletter_draft = Newsletter(**loaded_draft_data) # Reconstruct Newsletter object
        print("Loaded newsletter draft from file.")
    else:
        print("\nWARNING: No newsletter_draft_state.json found or it's empty. Using dummy draft for testing.")
        # Create a dummy newsletter draft for testing (simulate a good one)
        good_draft = Newsletter(
            date=datetime.now(),
            subject=f"{settings.NEWSLETTER_SUBJECT_PREFIX} 2025-07-25 Test Draft", # Updated date for consistency
            content_markdown="""## Introduction
This is a test introduction for a good newsletter. It has 3-4 sentences. It sets the stage well. This looks fine.

## Featured Article
### Test Article Title
- Summary: This is a test summary for a good article. It's concise and relevant.
[Read More](https://example.com/test-good-article)

## Conclusion
This is a test conclusion for a good newsletter. It has 2-3 sentences. It wraps up the content effectively.

**Overall Trends:**
- Test trend 1
- Test trend 2
""",
            is_approved=False,
            revision_attempts=0
        )
        loaded_newsletter_draft = good_draft
    
    # Try loading summarized_content (needed for factual checks by LLM)
    loaded_summarized_content_data = load_state_from_json("summarized_content_state.json", DATA_DIR).get('summarized_content', [])
    loaded_summarized_content = [SummarizedContent(**item) for item in loaded_summarized_content_data] if loaded_summarized_content_data else []
    if not loaded_summarized_content:
        print("\nWARNING: No summarized_content_state.json found or it's empty. Using dummy summarized content for factual verification.")
        dummy_summarized_content_for_factual_check = [
            SummarizedContent(
                original_url="https://example.com/test-good-article",
                title="Test Article Title",
                summary="This is the factual content for the test article. It is accurate and concise.",
                key_entities=["Test Entity"],
                trends_identified=["Test Trend"]
            )
        ]
        loaded_summarized_content = dummy_summarized_content_for_factual_check


    # Initial state for Editorial Agent
    initial_state: AgentState = {
        "raw_articles": [],
        "summarized_content": loaded_summarized_content, # Provide summarized content for factual check
        "newsletter_outline": None,
        "newsletter_draft": loaded_newsletter_draft,
        "revision_needed": False,
        "revision_attempts": 0, # First attempt for testing
        "newsletter_sent": False,
        "delivery_report": None,
        "recipients": [],
    }

    # Run the editorial agent node
    updated_state = editorial_agent_node(initial_state)
    draft_final = updated_state['newsletter_draft']

    print(f"\n--- Editorial Agent Review Results ---")
    print(f"Draft Subject: {draft_final.subject}")
    print(f"Is Approved: {draft_final.is_approved}")
    print(f"Approval Score: {draft_final.approval_score:.2f}" if draft_final.approval_score is not None else "N/A")
    print(f"Feedback: {draft_final.feedback}")
    print(f"Revision Needed (State): {updated_state['revision_needed']}")
    print(f"Revision Attempts (State): {updated_state['revision_attempts']}")
    
    # --- Save final newsletter_draft state ---
    save_state_to_json({"newsletter_draft": updated_state['newsletter_draft']}, "final_newsletter_draft_state.json", DATA_DIR)
    print(f"\nSaved final_newsletter_draft to {DATA_DIR / 'final_newsletter_draft_state.json'}")
    
    if updated_state['revision_needed']:
        print("\nNewsletter needs revision. You might want to re-run generation, or fix the prompt!")
    elif draft_final.is_approved:
        print("\nNewsletter approved! Ready for delivery.")
    else:
        print("\nNewsletter not approved and max revisions reached. Workflow terminates here.")