import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import get_settings
from src.utils import logger
from src.tools.llm_interface import get_default_llm
from src.models.newsletter_models import NewsletterOutline, Newsletter # Ensure all models are imported, as you correctly noted
# from src.models.newsletter_models import NewsletterOutline, Newsletter, NewsletterSection, NewsletterArticle # Already imported from above, but good to be explicit for clarity
from src.prompts.generation_prompts import GENERATION_PROMPT
from src.state import AgentState

settings = get_settings()
generation_llm = get_default_llm()

def generation_agent_node(state: AgentState) -> AgentState:
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
    
    newsletter_outline_json_str = newsletter_outline.model_dump_json(indent=2)
    current_date_formatted = datetime.now().strftime('%Y-%m-%d')

    try:
        logger.info("GENERATION AGENT: Invoking LLM to draft the newsletter content.")
        prompt = GENERATION_PROMPT.format(
            current_date=current_date_formatted,
            newsletter_outline_json=newsletter_outline_json_str
        )
        response_content = generation_llm.invoke(prompt)

        # --- MORE ROBUST MARKDOWN AND SUBJECT EXTRACTION ---
        
        # 1. Attempt to extract subject first, as it might appear anywhere at the beginning
        generated_subject = f"{settings.NEWSLETTER_SUBJECT_PREFIX}{current_date_formatted} Updates" # Default fallback

        # Pattern to find a subject line potentially at the very start of the response,
        # or inside markdown headings, possibly with our prefix.
        # This will look for a line that contains the prefix, possibly at the start of the string or after newlines.
        # We capture the line itself.
        subject_line_prefix_escaped = re.escape(settings.NEWSLETTER_SUBJECT_PREFIX.strip())
        subject_match = re.search(
            r"(^|\n)(#+\s*)?(" + subject_line_prefix_escaped + r".*)$", 
            response_content, 
            re.MULTILINE | re.IGNORECASE
        )
        
        if subject_match:
            full_subject_line = subject_match.group(3).strip() # Capture group 3 contains the actual subject text after our prefix
            # Remove Markdown heading characters if present (e.g., "## ")
            generated_subject = re.sub(r"^#+\s*", "", full_subject_line).strip()
            
            # Ensure it starts with the desired prefix if not already
            if not generated_subject.startswith(settings.NEWSLETTER_SUBJECT_PREFIX.strip()):
                generated_subject = f"{settings.NEWSLETTER_SUBJECT_PREFIX.strip()}{generated_subject}"
            
            logger.info(f"GENERATION AGENT: Extracted subject line: '{generated_subject}'")
        else:
            logger.warning("GENERATION AGENT: Could not extract specific subject line from LLM response. Using fallback.")
            
        # 2. Extract content markdown, removing code blocks and preamble
        content_markdown = response_content.strip()

        # Remove common preamble phrases from LLMs at the start
        preamble_patterns = [
            r"^Here is the generated newsletter content in Markdown format:[\n\s]*",
            r"^Here is the analysis of the article:[\n\s]*", # From previous agent's debug output
            r"^Here is your newsletter:[\n\s]*",
            r"^Sure, here is your newsletter:[\n\s]*",
            r"^(```json\s*\{.*?\}(```)?)\s*\n*", # Remove any leftover JSON blocks from earlier debugging
            r"^(```markdown)?\s*\n*", # Remove ```markdown or ``` at the very start
            r"^\s*Subject:.*?\n+", # Remove subject line if it was at the very start and we already extracted it
            r"^(AI Agent Weekly Digest:.*?\n)+" # Remove fallback subject line if it was also included by LLM
        ]
        for pattern in preamble_patterns:
            content_markdown = re.sub(pattern, "", content_markdown, flags=re.IGNORECASE | re.DOTALL).strip()
        
        # Remove ``` at the end if present (from the markdown block)
        if content_markdown.endswith("```"):
            content_markdown = content_markdown[:-len("```")].strip()
        
        # Remove the extracted subject line from the main content, only if it still exists there
        # This prevents duplication if the LLM wrote it inside the markdown body
        if generated_subject.strip() in content_markdown:
             # Try to remove the first occurrence of the subject line from content markdown
             content_markdown = content_markdown.replace(generated_subject.strip(), "", 1).strip()
             # Also remove markdown headers if subject was part of a header, like "## Subject"
             content_markdown = re.sub(r"^(#+\s*)?" + re.escape(generated_subject.strip()) + r"\n*", "", content_markdown, flags=re.MULTILINE).strip()


        newsletter_draft = Newsletter(
            date=datetime.now(),
            subject=generated_subject, # Use the extracted/fallback subject
            content_markdown=content_markdown,
            is_approved=False,
            revision_attempts=state.get('revision_attempts', 0)
        )
        logger.info("---GENERATION AGENT: Successfully generated newsletter draft.---")

    except Exception as e:
        logger.error(f"GENERATION AGENT: Error during LLM invocation or content parsing: {e}", exc_info=True)
        newsletter_draft = Newsletter(
            date=datetime.now(),
            subject=f"{settings.NEWSLETTER_SUBJECT_PREFIX} Generation Failed",
            content_markdown="## Newsletter Generation Failed\n\nUnfortunately, a critical error "
                             "occurred during the generation of this week's newsletter content. "
                             "Please check the system logs for more details.",
            is_approved=False
        )

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