import json
import re # For robust JSON parsing in case LLM adds filler
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import get_settings
from src.utils import logger
from src.tools.llm_interface import get_default_llm # Our LLM interface
from src.models.newsletter_models import NewsletterOutline, Newsletter, NewsletterSection, NewsletterArticle # New models
from src.prompts.generation_prompts import GENERATION_PROMPT
from src.state import AgentState # Our shared state definition

# Load application settings
settings = get_settings()

# Initialize the LLM for this agent
generation_llm = get_default_llm()

def generation_agent_node(state: AgentState) -> AgentState:
    """
    Newsletter Generation Agent node: Takes the structured outline and
    generates the full newsletter content in Markdown format.
    - Uses an LLM to expand the outline into a complete newsletter.
    - Creates the Newsletter object with subject and markdown content.
    - Updates the 'newsletter_draft' field in the state.
    """
    logger.info("---GENERATION AGENT: Starting newsletter content generation---")

    newsletter_outline: Optional[NewsletterOutline] = state.get('newsletter_outline')
    if not newsletter_outline:
        logger.error("GENERATION AGENT: No newsletter outline found in state. Cannot generate newsletter.")
        new_state = state.copy()
        new_state['newsletter_draft'] = Newsletter(
            date=datetime.now(),
            subject=f"{settings.NEWSLETTER_SUBJECT_PREFIX} Generation Failed",
            content_markdown="## Newsletter Generation Failed\n\nUnfortunately, an error occurred "
                             "during the generation of this week's newsletter outline. "
                             "Please check the system logs for more details.",
            is_approved=False
        )
        return new_state
    
    # Prepare the outline for the LLM prompt (convert to JSON string)
    newsletter_outline_json_str = newsletter_outline.model_dump_json(indent=2)
    
    current_date_formatted = datetime.now().strftime('%Y-%m-%d')

    try:
        logger.info("GENERATION AGENT: Invoking LLM to draft the newsletter content.")
        prompt = GENERATION_PROMPT.format(
            current_date=current_date_formatted,
            newsletter_outline_json=newsletter_outline_json_str
        )
        response_content = generation_llm.invoke(prompt)

        # The LLM is instructed to give *only* markdown content.
        # However, sometimes LLMs still wrap it in markdown code blocks or add preamble.
        # We need to strip any common markdown code block wrappers if present.
        # Check if it starts with a common markdown block for code or general conversation
        if response_content.strip().startswith("```markdown"):
            content_markdown = response_content.strip()[len("```markdown"):]
            if content_markdown.strip().endswith("```"):
                content_markdown = content_markdown.strip()[:-len("```")]
        elif response_content.strip().startswith("```"): # Generic code block
            content_markdown = response_content.strip()[len("```"):]
            if content_markdown.strip().endswith("```"):
                content_markdown = content_markdown.strip()[:-len("```")]
        else:
            content_markdown = response_content.strip() # Assume it's already clean markdown

        # Extract subject line - assume first line is subject, or look for specific pattern
        subject_line_prefix = settings.NEWSLETTER_SUBJECT_PREFIX.strip()
        # Regex to find a line starting with subject prefix, case-insensitive, possibly with ## or #
        subject_match = re.search(r"^(#+\s*)?" + re.escape(subject_line_prefix) + r".*$", content_markdown, re.MULTILINE | re.IGNORECASE)
        
        generated_subject = f"{subject_line_prefix}{current_date_formatted} Updates" # Default fallback
        if subject_match:
            full_subject_line = subject_match.group(0).strip()
            # Remove markdown headings like "## "
            generated_subject = re.sub(r"^#+\s*", "", full_subject_line).strip()
            # Ensure it starts with the desired prefix if not already
            if not generated_subject.startswith(subject_line_prefix):
                generated_subject = f"{subject_line_prefix}{generated_subject}"
            
            # Remove the subject line from the content_markdown
            content_markdown = content_markdown.replace(full_subject_line, "", 1).strip()
            logger.info(f"GENERATION AGENT: Extracted subject line: '{generated_subject}'")
        else:
            logger.warning("GENERATION AGENT: Could not extract subject line from LLM response. Using fallback.")
            
        # Optional: Further cleanup of content_markdown if LLM added any other preamble/postamble
        # For instance, if it started with "Here is your newsletter:"
        content_markdown = re.sub(r"^(Here is your newsletter:|Sure, here is your newsletter:)\s*\n*", "", content_markdown, flags=re.IGNORECASE).strip()


        newsletter_draft = Newsletter(
            date=datetime.now(),
            subject=generated_subject,
            content_markdown=content_markdown,
            is_approved=False, # Will be set by Editorial Agent
            revision_attempts=state.get('revision_attempts', 0)
        )
        logger.info("---GENERATION AGENT: Successfully generated newsletter draft.---")

    except Exception as e:
        logger.error(f"GENERATION AGENT: Error during LLM invocation or content parsing: {e}", exc_info=True)
        # Fallback for critical generation failure
        newsletter_draft = Newsletter(
            date=datetime.now(),
            subject=f"{settings.NEWSLETTER_SUBJECT_PREFIX} Generation Failed",
            content_markdown="## Newsletter Generation Failed\n\nUnfortunately, a critical error "
                             "occurred during the generation of this week's newsletter content. "
                             "Please check the system logs for more details.",
            is_approved=False
        )

    # Update the state with the newsletter draft
    new_state = state.copy()
    new_state['newsletter_draft'] = newsletter_draft
    return new_state


# Example usage (for testing purposes)
if __name__ == "__main__":
    print("--- Testing Generation Agent Node (Standalone) ---")

    # Create a dummy newsletter outline for testing
    dummy_newsletter_outline = NewsletterOutline(
        date=datetime.now(),
        introduction_points=[
            "This week, we dive into groundbreaking advancements in AI agent collaboration.",
            "Expect insights on new multi-agent frameworks and their practical applications."
        ],
        sections=[
            NewsletterSection(
                name="Top Insights & Breakthroughs",
                articles=[
                    NewsletterArticle(
                        title="LangGraph New Features: Cycles and Memory",
                        summary="LangGraph introduces explicit cycles and memory management, enabling complex multi-agent conversations and long-term context retention.",
                        url="https://example.com/langgraph-new-features",
                        category="New Frameworks & Tools"
                    )
                ]
            ),
            NewsletterSection(
                name="Ethical & Societal Impact",
                articles=[
                    NewsletterArticle(
                        title="AI Ethics in Multi-Agent Systems",
                        summary="Embedding ethics into multi-agent systems for fairness, transparency, and accountability in autonomous decision-making.",
                        url="https://example.com/ai-ethics-multi-agent",
                        category="Ethical & Societal Impact"
                    )
                ]
            ),
            NewsletterSection(
                name="Research & Academic Highlights",
                articles=[
                    NewsletterArticle(
                        title="A Survey on Autonomous Agents for Scientific Discovery",
                        summary="Autonomous agents accelerate scientific discovery through experiment design, data analysis, and hypothesis formulation using reinforcement learning and natural language processing.",
                        url="https://example.com/arxiv-scientific-discovery",
                        category="Research & Academic Highlights"
                    )
                ]
            )
        ],
        conclusion_points=[
            "The field of AI agents continues to evolve rapidly, promising more autonomous and intelligent systems.",
            "Stay tuned for more updates next week as we track these exciting developments."
        ],
        overall_trends=["Multi-agent collaboration", "Ethical AI in practice", "Autonomous research"]
    )

    # Initialize a dummy state with the newsletter outline
    initial_state: AgentState = {
        "raw_articles": [],
        "summarized_content": [],
        "newsletter_outline": dummy_newsletter_outline,
        "newsletter_draft": None, # This will be populated by the agent
        "revision_needed": False,
        "revision_attempts": 0,
    }

    # Run the generation agent node
    updated_state = generation_agent_node(initial_state)

    print(f"\n--- Generated Newsletter Draft ---")
    if updated_state['newsletter_draft']:
        draft = updated_state['newsletter_draft']
        print(f"Subject: {draft.subject}")
        print(f"\nContent (Markdown):\n{draft.content_markdown}")
        print(f"\nIs Approved: {draft.is_approved}")
        print(f"Revision Attempts: {draft.revision_attempts}")
    else:
        print("No newsletter draft generated. Check logs for errors.")