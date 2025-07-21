import os
from typing import List, Dict, Any, TypedDict
from datetime import datetime

from src.config import get_settings
from src.utils import logger
from src.tools.serper_dev import serper_search_tool # Our web search tool
from src.tools.rss_parser import rss_parser_tool_instance # Our RSS parser
from src.tools.arxiv_search import arxiv_search_tool_instance # Our arXiv search tool
from src.models.research_models import RawArticle # Our Pydantic model for raw articles
from src.state import AgentState

# Load application settings
settings = get_settings()

# Define the state for the LangGraph workflow
# We use TypedDict for clearer state structure
class AgentState(TypedDict):
    """
    Represents the state of the AI Agent News Agent workflow.
    This state will be passed between LangGraph nodes.
    """
    raw_articles: List[RawArticle]
    # We will add more fields here as we implement other agents
    # For now, initialize with an empty list for raw_articles

def research_agent_node(state: AgentState) -> AgentState:
    """
    Research Agent node: Gathers raw articles from various sources.
    - Performs web searches using SerperDev.
    - Parses RSS feeds.
    - Searches arXiv for academic papers.
    - De-duplicates articles based on URL.
    - Updates the 'raw_articles' field in the state.
    """
    logger.info("---RESEARCH AGENT: Starting information gathering---")

    search_keywords = settings.get_research_keywords_list()
    rss_feed_urls = settings.get_research_rss_feeds_list()
    max_articles = settings.RESEARCH_MAX_ARTICLES_PER_RUN

    all_fetched_articles: List[RawArticle] = []
    seen_urls = set()

    # 1. Web Search (using SerperDev tool)
    logger.info(f"RESEARCH AGENT: Performing web searches for {len(search_keywords)} keywords.")
    for keyword in search_keywords:
        try:
            # Invoke the Serper search tool
            results = serper_search_tool.invoke({"query": keyword, "num_results": max_articles // len(search_keywords) or 1})
            for res in results:
                url = res.get('link')
                if url and url not in seen_urls:
                    all_fetched_articles.append(RawArticle(
                        title=res.get('title', 'No Title'),
                        url=url,
                        content=res.get('snippet', 'No Snippet'), # Using snippet as initial content
                        source="web_search"
                    ))
                    seen_urls.add(url)
        except Exception as e:
            logger.error(f"RESEARCH AGENT: Error during web search for '{keyword}': {e}")

    # 2. RSS Feed Parsing (using RSS parser tool)
    logger.info(f"RESEARCH AGENT: Parsing {len(rss_feed_urls)} RSS feeds.")
    for feed_url in rss_feed_urls:
        try:
            articles = rss_parser_tool_instance.parse_feed(feed_url, limit=max_articles // len(rss_feed_urls) or 1)
            for article_data in articles:
                url = article_data.get('link')
                if url and url not in seen_urls:
                    all_fetched_articles.append(RawArticle(
                        title=article_data.get('title', 'No Title'),
                        url=url,
                        content=article_data.get('summary', 'No Summary'),
                        source="rss_feed"
                    ))
                    seen_urls.add(url)
        except Exception as e:
            logger.error(f"RESEARCH AGENT: Error during RSS feed parsing for '{feed_url}': {e}")

    # 3. ArXiv Search (using arXiv search tool)
    logger.info(f"RESEARCH AGENT: Searching arXiv for academic papers.")
    for keyword in search_keywords: # Re-using keywords for arXiv search
        try:
            papers = arxiv_search_tool_instance.search_arxiv(keyword, max_results=max_articles // len(search_keywords) // 2 or 1) # Fewer arXiv results
            for paper_data in papers:
                url = paper_data.get('link')
                if url and url not in seen_urls:
                    all_fetched_articles.append(RawArticle(
                        title=paper_data.get('title', 'No Title'),
                        url=url,
                        content=paper_data.get('summary', 'No Summary'),
                        source="arxiv_paper"
                    ))
                    seen_urls.add(url)
        except Exception as e:
            logger.error(f"RESEARCH AGENT: Error during arXiv search for '{keyword}': {e}")


    # Limit total articles if needed (though already limited by individual calls)
    final_articles = all_fetched_articles[:max_articles]
    logger.info(f"---RESEARCH AGENT: Completed. Fetched {len(final_articles)} unique articles.---")

    # Update the state with the fetched articles
    new_state = state.copy() # Make a mutable copy of the state
    new_state['raw_articles'] = final_articles
    return new_state

# Example usage (for testing purposes) - will not run with main.py for LangGraph
if __name__ == "__main__":
    # This is a standalone test of the node's logic.
    # In a real LangGraph flow, this node would receive a state from the graph.

    print("--- Testing Research Agent Node (Standalone) ---")
    
    # Initialize a dummy state with all required keys from AgentState
    initial_state: AgentState = {
        "raw_articles": [],
        "summarized_content": [], # Initialize new keys
        "newsletter_outline": None,
        "newsletter_draft": None,
        "revision_needed": False,
        "revision_attempts": 0,
    }

    # Run the research agent node
    updated_state = research_agent_node(initial_state)

    print(f"\nTotal articles fetched: {len(updated_state['raw_articles'])}")
    for i, article in enumerate(updated_state['raw_articles'][:5]): # Print first 5 for review
        print(f"\nArticle {i+1}:")
        print(f"Title: {article.title}")
        print(f"URL: {article.url}")
        print(f"Source: {article.source}")
        print(f"Content (snippet): {article.content[:200]}...") # Limit content output
    
    if not updated_state['raw_articles']:
        print("\nNo articles fetched. Please check .env configuration for API keys, RSS feeds, and keywords.")
        print("Ensure Ollama/HuggingFace LLM is running for other steps, though not directly used by this node yet.")