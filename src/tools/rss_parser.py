import feedparser
from src.utils import logger
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.config import get_settings

class RSSParserTool:
    """
    A utility to parse RSS feeds and extract relevant article information.
    """
    def __init__(self):
        logger.info("RSSParserTool initialized.")

    def parse_feed(self, url: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Parses a given RSS feed URL and returns a list of articles.
        Args:
            url (str): The URL of the RSS feed.
            limit (Optional[int]): Maximum number of articles to return.
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing an article
                                  with 'title', 'link', 'summary', 'published'.
        """
        logger.info(f"Attempting to parse RSS feed: {url}")
        articles = []
        try:
            feed = feedparser.parse(url)
            if feed.bozo:
                logger.warning(f"RSS feed '{url}' might be malformed: {feed.bozo_exception}")

            for i, entry in enumerate(feed.entries):
                if limit and i >= limit:
                    break
                
                title = entry.get('title', 'No Title')
                link = entry.get('link', 'No Link')
                
                # Try to get summary from 'summary', 'description', or 'content'
                summary = entry.get('summary', entry.get('description', 'No Summary'))
                if not summary and hasattr(entry, 'content') and entry.content:
                    summary = entry.content[0].value # Take the first content element

                published_date_str = entry.get('published', entry.get('updated', ''))
                published_date = None
                if published_date_str:
                    try:
                        # feedparser usually handles various date formats, but sometimes it helps
                        # to explicitly convert to datetime object if feedparser's parsing is inconsistent.
                        # For now, we'll rely on feedparser's internal parsing to a struct_time,
                        # but if raw_timestamp is needed, further parsing of published_parsed is required.
                        pass
                    except Exception as date_e:
                        logger.warning(f"Could not parse date '{published_date_str}' from {link}: {date_e}")

                articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published_date_str # Keep as string for simplicity, or convert to datetime
                })
            logger.info(f"Successfully parsed {len(articles)} articles from RSS feed: {url}")
            return articles
        except Exception as e:
            logger.error(f"Error parsing RSS feed '{url}': {e}", exc_info=True)
            return []

# Instantiate the tool
rss_parser_tool_instance = RSSParserTool()

# Example usage (for testing purposes)
if __name__ == "__main__":
    # Add some real RSS feed URLs to your .env config for testing
    # Example: RESEARCH_RSS_FEEDS="https://www.theverge.com/rss/index.xml,https://techcrunch.com/feed/"
    
    settings = get_settings()
    sample_rss_feeds = settings.get_research_rss_feeds_list()

    if not sample_rss_feeds:
        print("No RSS feeds configured in .env for testing. Add some to RESEARCH_RSS_FEEDS.")
        # Fallback to a well-known feed for demo if none configured
        sample_rss_feeds = ["https://hnrss.org/frontpage?points=300", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"]
        print(f"Using fallback RSS feeds for demonstration: {sample_rss_feeds}")

    all_rss_articles = []
    for feed_url in sample_rss_feeds:
        articles = rss_parser_tool_instance.parse_feed(feed_url, limit=2) # Get 2 articles from each
        if articles:
            print(f"\n--- Articles from {feed_url} ---")
            for article in articles:
                print(f"Title: {article.get('title')}")
                print(f"Link: {article.get('link')}")
                print(f"Summary: {article.get('summary')[:100]}...") # Print first 100 chars
                print(f"Published: {article.get('published')}\n")
            all_rss_articles.extend(articles)
        else:
            print(f"No articles or error for feed: {feed_url}")

    if all_rss_articles:
        print(f"\nTotal RSS articles fetched: {len(all_rss_articles)}")