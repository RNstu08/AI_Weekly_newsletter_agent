from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class RawArticle(BaseModel):
    """
    Represents a raw article fetched by the Research Agent.
    """
    title: str = Field(..., description="Title of the article.")
    url: str = Field(..., description="URL of the article.")
    content: Optional[str] = Field(None, description="Full text content of the article, if available.")
    source: str = Field(..., description="Source (e.g., 'web_search', 'rss_feed', 'arxiv').")
    fetch_timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp when the article was fetched.")

class SummarizedContent(BaseModel):
    """
    Represents content after extraction and summarization by the Extraction Agent.
    """
    original_url: str = Field(..., description="Original URL of the article.")
    title: str = Field(..., description="Title of the summarized content.")
    summary: str = Field(..., description="Concise summary of the article.")
    key_entities: List[str] = Field(default_factory=list, description="List of key entities mentioned (e.g., agent names, frameworks).")
    trends_identified: List[str] = Field(default_factory=list, description="List of overarching trends identified.")
    relevance_score: Optional[float] = Field(None, description="Relevance score assigned by Curation Agent (0.0 to 1.0).")
    category: Optional[str] = Field(None, description="Assigned category for the newsletter section.")