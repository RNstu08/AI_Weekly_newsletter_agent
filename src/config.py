import os
from functools import lru_cache
from pydantic import BaseSettings
from typing import List, Optional

# Import Streamlit for secrets management. Handle ImportError for local non-Streamlit runs.
try:
    import streamlit as st
except ImportError:
    st = None # Set st to None if Streamlit is not installed (e.g., when running locally outside Streamlit)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    On Streamlit Cloud, this configuration will explicitly pull from st.secrets.
    """
    # Use Config class for pydantic v1.x settings
    class Config:
        env_file = '.env' # Still respects .env for local development

        # Custom method to tell pydantic-settings where to find secrets, prioritizing Streamlit's st.secrets
        @classmethod
        def customise_sources(
            cls,
            init_settings, # settings passed to the constructor
            env_settings,  # settings loaded from environment variables
            file_secret_settings, # settings loaded from pydantic's default secrets logic
        ):
            # Prioritize Streamlit secrets if running in Streamlit environment
            # Then standard environment variables
            # Then .env file
            return (
                init_settings,
                st_secrets_settings_factory, # Custom source for Streamlit secrets
                env_settings,
                file_secret_settings,
            )

    # LLM Configuration (Set to HuggingFace for Streamlit Cloud compatibility)
    LLM_PROVIDER: str = "huggingface" # Must be "huggingface" for cloud deployment
    OLLAMA_BASE_URL: str = "http://localhost:11434" # Keep for local testing if needed
    OLLAMA_MODEL_NAME: str = "llama3" # Keep for local testing if needed

    # API Keys
    # These will be populated from Streamlit Secrets (or .env locally)
    SERPER_API_KEY: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None

    # Hugging Face API Token and Model Name (used when LLM_PROVIDER is "huggingface")
    HF_API_TOKEN: Optional[str] = None
    HF_MODEL_NAME: Optional[str] = "mistralai/Mistral-7B-Instruct-v0.2" # Example model

    # Newsletter Specific Settings
    NEWSLETTER_RECIPIENTS: str = "exampledemo8@gmail.com" # Comma-separated list
    NEWSLETTER_SENDER_EMAIL: str = "exampledemo8@gmail.com" # Must be a verified sender in SendGrid
    NEWSLETTER_SUBJECT_PREFIX: str = "AI Agent Weekly Digest: "

    # Research Agent Settings
    RESEARCH_KEYWORDS: str = "AI agent development, multi-agent systems, autonomous agents, langchain, langgraph, crewai, agentic workflows, LLM agents"
    RESEARCH_RSS_FEEDS: str = "https://news.ycombinator.com/rss,https://techcrunch.com/feed/"
    RESEARCH_MAX_ARTICLES_PER_RUN: int = 20

    # Content Limits (for LLM context management)
    MAX_SUMMARY_LENGTH: int = 300
    MAX_ARTICLE_CHUNK_SIZE: int = 4000

    # Editorial Agent Settings
    EDITORIAL_MIN_QUALITY_SCORE: float = 0.7
    EDITORIAL_MAX_REVISION_ATTEMPTS: int = 2

    # Scheduling (for run_weekly_job.py - not directly used by Streamlit UI, but consistent config)
    WEEKLY_SEND_DAY: str = "Friday"
    WEEKLY_SEND_TIME: str = "10:00"

# FIX: Custom settings source function to read from Streamlit's st.secrets
def st_secrets_settings_factory(settings_cls):
    """
    A custom settings source factory for pydantic-settings that reads directly from Streamlit's st.secrets.
    It flattens nested secrets and uppercases keys to match typical pydantic-settings/env var conventions.
    """
    if st and hasattr(st, 'secrets'):
        secrets_from_st = {}
        for k, v in st.secrets.items():
            if isinstance(v, dict): # Handle nested secrets (e.g., [connections.database])
                for sub_k, sub_v in v.items():
                    # Flatten nested keys with an underscore and uppercase them
                    secrets_from_st[f"{k.upper()}_{sub_k.upper()}"] = sub_v
            else:
                secrets_from_st[k.upper()] = v # Uppercase top-level keys
        
        # pydantic-settings expects a dictionary of values for a custom source
        return secrets_from_st
    return {} # Return empty dict if st.secrets is not available (e.g., during local non-Streamlit run)


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    This uses the customized sources to prioritize Streamlit secrets.
    """
    return Settings()