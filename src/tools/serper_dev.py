from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import StructuredTool
from src.config import get_settings
from src.utils import logger
from typing import Dict, List, Any, Type # Import Type
from pydantic import BaseModel, Field # Import BaseModel and Field
from src.config import get_settings # <--- This is correct here

# Load settings to get the API key
settings = get_settings()

# Define the Pydantic BaseModel for the tool's input arguments
class SerperSearchInput(BaseModel):
    """Input schema for Serper web search."""
    query: str = Field(description="The search query string.")
    num_results: int = Field(default=5, description="The maximum number of results to return.")

class SerperSearchTool:
    """
    A wrapper for the Google Serper API to perform web searches.
    """
    def __init__(self):
        if not settings.SERPER_API_KEY:
            logger.error("SERPER_API_KEY not found in environment variables. Web search will not function.")
            raise ValueError("SERPER_API_KEY is required for SerperSearchTool.")
        self.serper_api_wrapper = GoogleSerperAPIWrapper(serper_api_key=settings.SERPER_API_KEY)
        logger.info("SerperSearchTool initialized.")

    def _run_search_web(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Performs a web search using Google Serper API and returns relevant results.
        Returns a list of dictionaries, each containing 'title', 'link', 'snippet'.
        Args:
            query (str): The search query.
            num_results (int): The maximum number of results to return (default is 5).
        """
        logger.info(f"Performing web search for query: '{query}' (limit: {num_results})")
        try:
            results = self.serper_api_wrapper.results(query)
            
            organic_results = results.get('organic', [])
            
            parsed_results = []
            for i, res in enumerate(organic_results):
                if i >= num_results:
                    break
                parsed_results.append({
                    "title": res.get("title"),
                    "link": res.get("link"),
                    "snippet": res.get("snippet")
                })

            logger.info(f"Web search for '{query}' completed. Found {len(parsed_results)} organic results.")
            return parsed_results
        except Exception as e:
            logger.error(f"Error during web search for '{query}': {e}", exc_info=True)
            return []

# Instantiate the class
serper_tool_instance = SerperSearchTool()

# Now create the LangChain Tool object FROM the instance method
serper_search_tool = StructuredTool.from_function(
    func=serper_tool_instance._run_search_web,
    name="search_web", # This is the name the LLM will see
    description="Performs a web search using Google Serper API and returns relevant results. "
                "Useful for finding current information, news, and general knowledge on the internet. "
                "Input must conform to the SerperSearchInput schema.",
    args_schema=SerperSearchInput, # <--- THIS IS THE KEY CHANGE
)


# Example usage (for testing purposes)
if __name__ == "__main__":
    # Ensure SERPER_API_KEY is set in your .env file
    
    search_query = "latest AI agent development frameworks"
    
    # Now, we directly invoke the `serper_search_tool` (which is a StructuredTool instance)
    results = serper_search_tool.invoke({"query": search_query, "num_results": 3})

    if results:
        print(f"\nSearch results for '{search_query}':")
        for i, res in enumerate(results):
            print(f"--- Result {i+1} ---")
            print(f"Title: {res.get('title')}")
            print(f"Link: {res.get('link')}")
            print(f"Snippet: {res.get('snippet')}\n")
    else:
        print(f"No results found or an error occurred for '{search_query}'.")

    search_query_error = "nonexistent_topic_xyz_123_abc"
    results_error = serper_search_tool.invoke({"query": search_query_error, "num_results": 1})
    if not results_error:
        print(f"Successfully handled no results for '{search_query_error}'.")