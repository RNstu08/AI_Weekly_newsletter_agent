from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class NewsletterArticle(BaseModel):
    """
    Represents a single article as it will appear in the newsletter.
    """
    title: str = Field(..., description="Title for the newsletter entry.")
    summary: str = Field(..., description="The generated summary for the newsletter.")
    url: str = Field(..., description="URL to the original source.")
    category: str = Field(..., description="Category this article belongs to (e.g., 'Top Insights', 'Agent Spotlight').") # Category is required as Curation Agent ensures one

class NewsletterSection(BaseModel):
    """
    Represents a section within the newsletter (e.g., "Top Insights").
    """
    name: str = Field(..., description="Name of the newsletter section.")
    articles: List[NewsletterArticle] = Field(default_factory=list, description="List of articles in this section.")

class NewsletterOutline(BaseModel):
    """
    Represents the structured outline of the weekly newsletter.
    """
    date: datetime = Field(default_factory=datetime.now, description="Date for which the newsletter is generated.")
    introduction_points: List[str] = Field(default_factory=list, description="Key points for the newsletter introduction.")
    sections: List[NewsletterSection] = Field(default_factory=list, description="List of structured sections for the newsletter.")
    conclusion_points: List[str] = Field(default_factory=list, description="Key points for the newsletter conclusion.")
    overall_trends: List[str] = Field(default_factory=list, description="Overarching trends identified for the week.")

class Newsletter(BaseModel):
    """
    Represents the complete, generated newsletter content.
    """
    date: datetime = Field(default_factory=datetime.now, description="Date of the newsletter.")
    subject: str = Field(..., description="Subject line for the email.")
    content_markdown: str = Field(..., description="Full newsletter content in Markdown format.")
    content_html: Optional[str] = Field(None, description="Full newsletter content in HTML format, derived from markdown.") # <--- CHANGED BACK TO Optional[str] = Field(None, ...)
    is_approved: bool = Field(False, description="Whether the newsletter has been approved by the Editorial Agent.")
    approval_score: Optional[float] = Field(None, description="Quality score from the Editorial Agent.")
    feedback: Optional[str] = Field(None, description="Feedback from the Editorial Agent if not approved.")
    revision_attempts: int = Field(0, description="Number of times the newsletter has been revised.")
    sent_timestamp: Optional[datetime] = Field(None, description="Timestamp when the newsletter was sent.")