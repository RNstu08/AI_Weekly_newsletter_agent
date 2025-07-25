import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    # LLM Settings
    LLM_PROVIDER: str = "ollama"  # or "huggingface"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL_NAME: str = "llama3" # e.g., "llama3", "mistral"
    HF_API_TOKEN: Optional[str] = None # For HuggingFaceHub
    HF_MODEL_NAME: Optional[str] = None # e.g., "google/flan-t5-xxl"

    # API Keys
    SERPER_API_KEY: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None

    # Research Agent Settings
    RESEARCH_KEYWORDS: str = "AI agent development, multi-agent systems, agentic workflows, LangChain agents, CrewAI, AutoGen"
    RESEARCH_RSS_FEEDS: str = "https://www.theverge.com/rss/index.xml,https://techcrunch.com/feed/,https://rss.arxiv.org/rss/cs" # Example RSS feeds
    RESEARCH_MAX_ARTICLES_PER_RUN: int = 15

    # Extraction Agent Settings
    # Renamed from EXTRACTION_MAX_SUMMARY_LENGTH to MAX_SUMMARY_LENGTH as seen in error
    MAX_SUMMARY_LENGTH: int = 500
    # Added MAX_ARTICLE_CHUNK_SIZE
    MAX_ARTICLE_CHUNK_SIZE: int = 4000 # Typical chunk size for LLM context window, adjust as needed

    # Editorial Agent Settings
    EDITORIAL_MIN_QUALITY_SCORE: float = 0.75
    EDITORIAL_MAX_REVISION_ATTEMPTS: int = 2

    # Newsletter Delivery Settings
    NEWSLETTER_SENDER_EMAIL: str = "your_sender_email@example.com"
    NEWSLETTER_RECIPIENTS: str = "your_recipient_email@example.com" # Comma-separated
    NEWSLETTER_SUBJECT_PREFIX: str = "AI Agent Weekly Digest:"

    def get_research_keywords_list(self) -> List[str]:
        return [k.strip() for k in self.RESEARCH_KEYWORDS.split(',') if k.strip()]

    def get_research_rss_feeds_list(self) -> List[str]:
        return [f.strip() for f in self.RESEARCH_RSS_FEEDS.split(',') if f.strip()]

    def get_newsletter_recipients_list(self) -> List[str]:
        return [r.strip() for r in self.NEWSLETTER_RECIPIENTS.split(',') if r.strip()]

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    """
    return Settings()