from typing import List, Optional, TypedDict
from src.models.research_models import RawArticle, SummarizedContent
from src.models.newsletter_models import NewsletterOutline, Newsletter # Import other models as we add them

class AgentState(TypedDict):
    """
    Represents the shared state of the AI Agent News Agent workflow.
    This state will be passed between LangGraph nodes.
    """
    raw_articles: List[RawArticle] # Populated by Research Agent
    summarized_content: List[SummarizedContent] # Populated by Extraction Agent
    # Add other state variables here as needed for subsequent agents:
    newsletter_outline: Optional[NewsletterOutline]
    newsletter_draft: Optional[Newsletter]
    revision_needed: bool # Flag for editorial feedback loop
    revision_attempts: int # Counter for revision attempts