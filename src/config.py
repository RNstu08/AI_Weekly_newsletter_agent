# src/config.py (Full code for clarity)
import os
from functools import lru_cache
from pydantic import BaseSettings # <<< Changed for Pydantic v1.x
from typing import List, Optional

try:
    import streamlit as st
except ImportError:
    st = None 

class Settings(BaseSettings):
    class Config: # <<< Changed for Pydantic v1.x
        env_file = '.env'
        @classmethod
        def customise_sources(
            cls,
            init_settings,
            env_settings,
            file_secret_settings,
        ):
            return (
                init_settings,
                st_secrets_settings_factory,
                env_settings,
                file_secret_settings,
            )

    LLM_PROVIDER: str = "huggingface"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL_NAME: str = "llama3" 
    HF_API_TOKEN: Optional[str] = None
    HF_MODEL_NAME: Optional[str] = "mistralai/Mistral-7B-Instruct-v0.2" 
    NEWSLETTER_RECIPIENTS: str = "your_recipient_email@example.com"
    NEWSLETTER_SENDER_EMAIL: str = "your_sender_email@example.com"
    NEWSLETTER_SUBJECT_PREFIX: str = "AI Agent Weekly Digest: "
    RESEARCH_KEYWORDS: str = "AI agent development, multi-agent systems, autonomous agents, langchain, langgraph, crewai, agentic workflows, LLM agents"
    RESEARCH_RSS_FEEDS: str = "https://news.ycombinator.com/rss,https://techcrunch.com/feed/"
    RESEARCH_MAX_ARTICLES_PER_RUN: int = 20
    MAX_SUMMARY_LENGTH: int = 300
    MAX_ARTICLE_CHUNK_SIZE: int = 4000
    EDITORIAL_MIN_QUALITY_SCORE: float = 0.7
    EDITORIAL_MAX_REVISION_ATTEMPTS: int = 2
    WEEKLY_SEND_DAY: str = "Friday"
    WEEKLY_SEND_TIME: str = "10:00"

def get_research_keywords_list(self) -> List[str]:
    return [k.strip() for k in self.RESEARCH_KEYWORDS.split(',') if k.strip()]
def get_research_rss_feeds_list(self) -> List[str]:
    return [f.strip() for f in self.RESEARCH_RSS_FEEDS.split(',') if f.strip()]
def get_newsletter_recipients_list(self) -> List[str]:
    return [r.strip() for r in self.NEWSLETTER_RECIPIENTS.split(',') if r.strip()]