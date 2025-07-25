import requests
from src.utils import logger
from typing import List, Dict, Any
import xml.etree.ElementTree as ET

class ArxivSearchTool:
    """
    A tool to search for academic papers on arXiv.
    """
    ARXIV_API_URL = "http://export.arxiv.org/api/query"

    def __init__(self):
        logger.info("ArxivSearchTool initialized.")

    def search_arxiv(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Searches arXiv for papers matching the query.
        Args:
            query (str): The search query.
            max_results (int): Maximum number of results to return.
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing an arXiv paper.
        """
        logger.info(f"Searching arXiv for papers matching: '{query}' (limit: {max_results})")
        params = {
            "search_query": query,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        articles = []
        try:
            response = requests.get(self.ARXIV_API_URL, params=params, timeout=10)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

            root = ET.fromstring(response.content)
            
            # Arxiv XML namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom',
                  'arxiv': 'http://arxiv.org/schemas/atom'}

            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text.strip() if entry.find('atom:title', ns) is not None else 'No Title'
                
                # Get link to the abstract page
                link_element = entry.find("atom:link[@rel='alternate']", ns)
                link = link_element.attrib['href'] if link_element is not None and 'href' in link_element.attrib else 'No Link'
                
                summary = entry.find('atom:summary', ns).text.strip() if entry.find('atom:summary', ns) is not None else 'No Summary'
                published = entry.find('atom:published', ns).text.strip() if entry.find('atom:published', ns) is not None else 'No Date'
                
                authors = [author.find('atom:name', ns).text for author in entry.findall('atom:author', ns) if author.find('atom:name', ns) is not None]

                articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published,
                    "authors": authors
                })
            
            logger.info(f"Successfully found {len(articles)} papers on arXiv for '{query}'.")
            return articles
        except requests.exceptions.RequestException as e:
            logger.error(f"Network or HTTP error searching arXiv for '{query}': {e}", exc_info=True)
            return []
        except ET.ParseError as e:
            logger.error(f"Failed to parse arXiv XML response for '{query}': {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while searching arXiv for '{query}': {e}", exc_info=True)
            return []

# Instantiate the tool
arxiv_search_tool_instance = ArxivSearchTool()

# Example usage (for testing purposes)
if __name__ == "__main__":
    search_query = "LLM agent collaboration"
    results = arxiv_search_tool_instance.search_arxiv(search_query, max_results=2)

    if results:
        print(f"\nArXiv search results for '{search_query}':")
        for i, res in enumerate(results):
            print(f"--- Paper {i+1} ---")
            print(f"Title: {res.get('title')}")
            print(f"Link: {res.get('link')}")
            print(f"Summary: {res.get('summary')[:200]}...") # Print first 200 chars
            print(f"Published: {res.get('published')}")
            print(f"Authors: {', '.join(res.get('authors', []))}\n")
    else:
        print(f"No arXiv results found or an error occurred for '{search_query}'.")

    search_query_no_results = "nonexistent_research_topic_12345"
    results_no_results = arxiv_search_tool_instance.search_arxiv(search_query_no_results, max_results=1)
    if not results_no_results:
        print(f"Successfully handled no results for arXiv query: '{search_query_no_results}'.")