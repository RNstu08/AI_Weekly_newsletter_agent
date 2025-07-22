import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import get_settings
from src.utils import logger
from src.tools.llm_interface import get_default_llm
from src.models.newsletter_models import NewsletterOutline, Newsletter, NewsletterSection, NewsletterArticle
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

        # --- REVISED ROBUST MARKDOWN AND SUBJECT EXTRACTION (FINAL VERSION FOR THIS STAGE) ---
        
        cleaned_content = response_content.strip()
        generated_subject = f"{settings.NEWSLETTER_SUBJECT_PREFIX}{current_date_formatted} Updates" # Default fallback

        # Step 1: Aggressively strip all known preambles, postambles, and markdown fences.
        preamble_and_fence_patterns = [
            r"^(```(?:markdown)?\s*\n)*", # Optional leading ```markdown or ```, potentially multiple times
            r"^(Here is the generated newsletter content in Markdown format:[\n\s]*)*",
            r"^(Here is the analysis of the article:[\n\s]*)*",
            r"^(Here is your newsletter:[\n\s]*)*",
            r"^(Sure, here is your newsletter:[\n\s]*)*",
            r"^(```json\s*\{.*?\}(```)?)\s*\n*", # Any leftover JSON blocks
            r"^(Please let me know if you need any further assistance.[\n\s]*)*", # Common LLM closing
            r"^(Let me know if you'd like me to clarify or expand on this response!.*)*$", # From previous runs, can be multiline
            r"^\s*Subject:[\s\S]*?(?=#\s*AI Agent Weekly Digest:)", # Remove "Subject: [content]" if it precedes the actual # heading
            r"^\s*Subject:.*?\n+", # Fallback to remove "Subject: [content]" on a single line
        ]
        
        for pattern in preamble_and_fence_patterns:
            cleaned_content = re.sub(pattern, "", cleaned_content, flags=re.IGNORECASE | re.DOTALL).strip()
        
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-len("```")].strip()

        # Step 2: Extract Subject Line from the now-cleaner content
        subject_line_prefix_escaped = re.escape(settings.NEWSLETTER_SUBJECT_PREFIX.strip())
        
        subject_match = re.search(
            r"^\s*#\s*(" + subject_line_prefix_escaped + r".*?)$", 
            cleaned_content, 
            re.MULTILINE | re.IGNORECASE
        )
        
        if subject_match:
            generated_subject = subject_match.group(1).strip()
            logger.info(f"GENERATION AGENT: Extracted subject line: '{generated_subject}'")
            
            cleaned_content = re.sub(
                r"^\s*#\s*" + re.escape(generated_subject) + r"\s*\n*", 
                "", 
                cleaned_content, 
                flags=re.MULTILINE | re.IGNORECASE, 
                count=1
            ).strip()
        else:
            logger.warning("GENERATION AGENT: Could not extract specific subject line from LLM response. Using fallback.")
            
        # Step 3: Final content cleanup for minor refinements

        # 3a. Remove Category lines (e.g., "Category: New Frameworks & Tools")
        cleaned_content = re.sub(r"^\s*Category:.*$", "", cleaned_content, flags=re.MULTILINE | re.IGNORECASE).strip()

        # 3b. Convert standalone URLs to "[Read More](URL)" markdown links
        # This targets URLs that are often on their own line or follow a hyphen/bullet point
        # It ensures we don't accidentally link text that just happens to contain a URL.
        # This is the most complex regex, and might need careful testing on diverse LLM outputs.
        # It looks for a URL that is either at the start of a line, or preceded by whitespace/hyphen/bullet.
        # And followed by end of line or whitespace.
        cleaned_content = re.sub(
            r"(^|\n|\s|-|\*)\s*(https?://[^\s\]\)]+)(\s*$|\n)", # Capture preamble, the URL, and postamble
            r"\1[Read More](\2)\3", # Reconstruct with markdown link, preserving pre/postamble
            cleaned_content, 
            flags=re.MULTILINE | re.IGNORECASE
        ).strip()
        
        # Fallback for URLs not caught by the above (e.g., URL is not on its own line)
        # This is less aggressive, only wraps if it's the very last thing on a line or followed by specific chars.
        # Or you might omit this if the above is good enough with prompt changes.
        # cleaned_content = re.sub(r"(https?://\S+)", r"[Read More](\1)", cleaned_content).strip()


        # 3c. Remove excessive blank lines (3 or more newlines become 2)
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content).strip()
        
        # 3d. Final trim in case of any remaining leading/trailing whitespace
        content_markdown = cleaned_content.strip()

        newsletter_draft = Newsletter(
            date=datetime.now(),
            subject=generated_subject,
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