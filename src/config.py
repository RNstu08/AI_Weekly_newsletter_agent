import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses pydantic_settings for robust configuration management.
    """
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    # API Keys for External Services
    SERPER_API_KEY: str
    SENDGRID_API_KEY: str

    # LLM Configuration
    LLM_PROVIDER: str = "ollama" # e.g., "ollama", "huggingface"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL_NAME: str = "llama3" # Example: "llama3", "mistral", "zephyr"

    HF_API_TOKEN: str | None = None # Optional for Hugging Face Inference API
    HF_MODEL_NAME: str | None = None # e.g., "mistralai/Mistral-7B-Instruct-v0.2"

    # Newsletter Specific Settings
    NEWSLETTER_RECIPIENTS: str # Comma-separated emails
    NEWSLETTER_SENDER_EMAIL: str
    NEWSLETTER_SUBJECT_PREFIX: str = "AI Agent Weekly Digest: "

    # Research Agent Settings
    RESEARCH_KEYWORDS: str = "AI agent development, multi-agent systems, autonomous agents, langchain, langgraph, crewai, agentic workflows, LLM agents"
    RESEARCH_RSS_FEEDS: str = "" # Comma-separated RSS feed URLs
    RESEARCH_MAX_ARTICLES_PER_RUN: int = 20

    # Content Limits
    MAX_SUMMARY_LENGTH: int = 300 # characters
    MAX_ARTICLE_CHUNK_SIZE: int = 4000 # tokens (for LLM context)

    # Editorial Agent Settings
    EDITORIAL_MIN_QUALITY_SCORE: float = 0.7 # 0.0 to 1.0
    EDITORIAL_MAX_REVISION_ATTEMPTS: int = 2

    # Scheduling
    WEEKLY_SEND_DAY: str = "Friday"
    WEEKLY_SEND_TIME: str = "10:00"

    def get_newsletter_recipients_list(self) -> List[str]:
        """Parses the comma-separated recipient string into a list."""
        return [email.strip() for email in self.NEWSLETTER_RECIPIENTS.split(',') if email.strip()]

    def get_research_keywords_list(self) -> List[str]:
        """Parses the comma-separated keywords string into a list."""
        return [keyword.strip() for keyword in self.RESEARCH_KEYWORDS.split(',') if keyword.strip()]

    def get_research_rss_feeds_list(self) -> List[str]:
        """Parses the comma-separated RSS feeds string into a list."""
        return [feed.strip() for feed in self.RESEARCH_RSS_FEEDS.split(',') if feed.strip()]

@lru_cache()
def get_settings() -> Settings:
    """
    Caches the settings object for efficient access across the application.
    Loads settings from .env file or environment variables.
    """
    return Settings()

# Example usage (for testing purposes, remove in final main.py if not needed)
if __name__ == "__main__":
    # Create a .env file based on .env.example with your actual keys for this to work
    # Or set environment variables directly
    # For a quick test, you can create a dummy .env:
    # echo "SERPER_API_KEY=dummy_serper_key" > .env
    # echo "SENDGRID_API_KEY=dummy_sendgrid_key" >> .env
    # echo "NEWSLETTER_RECIPIENTS=test@example.com" >> .env
    # echo "NEWSLETTER_SENDER_EMAIL=test@yourdomain.com" >> .env
    # echo "OLLAMA_MODEL_NAME=dummy_model" >> .env # Add this for Ollama setup

    print("Loading settings...")
    settings = get_settings()
    print(f"LLM Provider: {settings.LLM_PROVIDER}")
    print(f"Ollama Model Name: {settings.OLLAMA_MODEL_NAME}")
    print(f"Newsletter Recipients: {settings.get_newsletter_recipients_list()}")
    print(f"Research Keywords: {settings.get_research_keywords_list()}")
    print(f"Max Summary Length: {settings.MAX_SUMMARY_LENGTH}")

    # Clean up dummy .env if created for testing
    # os.remove(".env")