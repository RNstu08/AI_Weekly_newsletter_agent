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
    newsletter_outline: Optional[NewsletterOutline] # Populated by Curation Agent
    newsletter_draft: Optional[Newsletter] # Populated by Generation Agent (and modified by Editorial)
    
    # Flags for editorial feedback loop and overall workflow control
    revision_needed: bool # True if Editorial Agent requests revision
    revision_attempts: int # Counter for revision attempts

    # Fields for Delivery Agent
    newsletter_sent: bool # True if the newsletter was successfully sent
    delivery_report: Optional[str] # Details about the delivery status (e.g., success message, error)