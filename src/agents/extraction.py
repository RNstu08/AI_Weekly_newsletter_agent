from typing import List, Dict, Any, Optional
import json
import re # <-- Add this import
from src.config import get_settings
from src.utils import logger
from src.tools.llm_interface import get_default_llm
from src.models.research_models import RawArticle, SummarizedContent
from src.prompts.extraction_prompts import EXTRACTION_PROMPT, RESUMMARIZE_PROMPT
from src.state import AgentState

# Load application settings
settings = get_settings()

# Initialize the LLM for this agent
extraction_llm = get_default_llm()

def extraction_agent_node(state: AgentState) -> AgentState:
    """
    Extraction Agent node: Processes raw articles to extract key insights,
    summarize content, and identify entities and trends using an LLM.
    - Iterates through 'raw_articles' in the state.
    - Uses LLM to summarize and extract.
    - Updates the 'summarized_content' field in the state.
    """
    logger.info("---EXTRACTION AGENT: Starting information extraction and summarization---")

    raw_articles: List[RawArticle] = state.get('raw_articles', [])
    if not raw_articles:
        logger.warning("EXTRACTION AGENT: No raw articles found in state. Skipping extraction.")
        new_state = state.copy()
        new_state['summarized_content'] = []
        return new_state

    summarized_results: List[SummarizedContent] = []

    for i, article in enumerate(raw_articles):
        logger.info(f"EXTRACTION AGENT: Processing article {i+1}/{len(raw_articles)}: {article.title}")
        try:
            max_llm_input_tokens = settings.MAX_ARTICLE_CHUNK_SIZE
            article_content = article.content if article.content else ""
            if len(article_content) > max_llm_input_tokens:
                logger.warning(f"Article content too long ({len(article_content)} chars). Truncating for LLM.")
                article_content = article_content[:max_llm_input_tokens] 

            formatted_prompt = EXTRACTION_PROMPT.format(
                max_summary_length=settings.MAX_SUMMARY_LENGTH,
                title=article.title,
                url=article.url,
                content=article_content
            )

            response_content = extraction_llm.invoke(formatted_prompt)
            
            # --- START OF MODIFIED JSON PARSING LOGIC ---
            json_str = ""
            try:
                # Regex to find JSON wrapped in ```json ... ``` or just { ... }
                # This pattern looks for the first '{' and the last '}'
                # allowing for any characters in between, non-greedily,
                # to catch cases where there's preamble/postamble.
                match = re.search(r"```json\s*(\{.*?\})\s*```|(\{.*?\})", response_content, re.DOTALL)
                
                if match:
                    if match.group(1): # Matched the ```json code block
                        json_str = match.group(1)
                    else: # Matched the bare JSON object
                        json_str = match.group(2)
                
                if not json_str: # Fallback if regex didn't find a JSON block
                    # Try to find the first '{' and last '}' as a last resort,
                    # assuming it might just be the raw JSON text with no wrapper
                    start_brace = response_content.find('{')
                    end_brace = response_content.rfind('}')
                    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                        json_str = response_content[start_brace : end_brace + 1]
                    else:
                        raise ValueError("No discernible JSON string found in LLM response.")

                parsed_llm_output = json.loads(json_str)

                summary = parsed_llm_output.get('summary', 'No summary provided.')
                # Ensure key_entities is a list, even if LLM gives a string
                key_entities = parsed_llm_output.get('key_entities', [])
                if isinstance(key_entities, str):
                    key_entities = [e.strip() for e in key_entities.split(',') if e.strip()]
                
                # Ensure trends_identified is a list, even if LLM gives a string
                trends_identified = parsed_llm_output.get('trends_identified', [])
                if isinstance(trends_identified, str):
                    trends_identified = [t.strip() for t in trends_identified.split(',') if t.strip()]

                # Ensure summary length constraint
                if len(summary) > settings.MAX_SUMMARY_LENGTH:
                    logger.warning(f"Summary for '{article.title}' is too long ({len(summary)} chars). Re-summarizing.")
                    shorten_prompt = RESUMMARIZE_PROMPT.format(
                        max_summary_length=settings.MAX_SUMMARY_LENGTH,
                        text=summary
                    )
                    shortened_summary_response = extraction_llm.invoke(shorten_prompt)
                    # Often LLMs still add conversational bits to shortened responses.
                    # Try to extract the core summary, simple stripping
                    summary = shortened_summary_response.strip().strip('"').strip("'")
                    
                    if len(summary) > settings.MAX_SUMMARY_LENGTH: # Final aggressive truncation
                         summary = summary[:settings.MAX_SUMMARY_LENGTH - 3] + "..." # -3 for ellipsis
                         logger.warning(f"Summary still too long after re-summarization, truncated: {summary[:50]}...")
                    else:
                        logger.info(f"Summary shortened to {len(summary)} characters.")

                summarized_results.append(SummarizedContent(
                    original_url=article.url,
                    title=article.title,
                    summary=summary,
                    key_entities=key_entities,
                    trends_identified=trends_identified
                ))
                logger.info(f"EXTRACTION AGENT: Successfully processed '{article.title}'.")

            except (json.JSONDecodeError, ValueError) as parse_e: # Catch ValueError from our custom parsing
                logger.error(f"EXTRACTION AGENT: Failed to parse JSON from LLM response for '{article.title}': {parse_e}. Raw response: '{response_content[:500]}...'")
                # Fallback to a simpler summary if JSON parsing fails
                summarized_results.append(SummarizedContent(
                    original_url=article.url,
                    title=article.title,
                    summary=article.content[:settings.MAX_SUMMARY_LENGTH] if article.content else "Could not process article (JSON parsing failed).",
                    key_entities=[],
                    trends_identified=[]
                ))
            except Exception as e:
                logger.error(f"EXTRACTION AGENT: Unexpected error processing LLM response for '{article.title}': {e}", exc_info=True)
                summarized_results.append(SummarizedContent(
                    original_url=article.url.strip(), # Ensure no leading/trailing whitespace on URL
                    title=article.title.strip(),
                    summary=article.content[:settings.MAX_SUMMARY_LENGTH] if article.content else "Could not process article (unexpected error).",
                    key_entities=[],
                    trends_identified=[]
                ))
        except Exception as e:
            logger.error(f"EXTRACTION AGENT: Error during LLM invocation for '{article.title}': {e}", exc_info=True)
            summarized_results.append(SummarizedContent(
                original_url=article.url.strip(),
                title=article.title.strip(),
                summary="Failed to summarize due to LLM invocation error.",
                key_entities=[],
                trends_identified=[]
            ))

    logger.info(f"---EXTRACTION AGENT: Completed. Processed {len(summarized_results)} articles.---")

    new_state = state.copy()
    new_state['summarized_content'] = summarized_results
    return new_state


# Example usage (for testing purposes)
if __name__ == "__main__":
    print("--- Testing Extraction Agent Node (Standalone) ---")

    # Create dummy raw articles for testing
    dummy_raw_articles = [
        RawArticle(
            title="LangGraph New Features: Cycles and Memory",
            url="https://example.com/langgraph-new-features",
            content="LangGraph recently introduced powerful new features including explicit cycles in graphs and enhanced memory management. This allows for more complex multi-agent conversations and improved long-term context retention. Developers can now easily create iterative workflows where agents can self-correct and refine their responses. The update also brings better integration with various vector databases for persistent memory. This is a game-changer for building sophisticated AI agents that can learn and adapt over time, pushing the boundaries of autonomous AI. The documentation has been updated to reflect these changes, providing clear examples for implementation. This advancement is crucial for enterprise-level applications requiring continuous learning and adaptability. More details are available on their official blog.",
            source="web_search"
        ),
        RawArticle(
            title="AI Ethics in Multi-Agent Systems",
            url="https://example.com/ai-ethics-multi-agent",
            content="The increasing complexity of multi-agent systems raises significant ethical concerns. Ensuring fairness, transparency, and accountability in autonomous decision-making processes is paramount. Researchers are exploring methods to embed ethical guidelines directly into agent architectures and to monitor emergent behaviors. Challenges include defining universal ethical principles and handling conflicting objectives among agents. This field is rapidly evolving, with new papers emerging on topics like moral reasoning in AI, value alignment, and human-agent cooperation. Future regulations may require robust ethical frameworks for deployed multi-agent systems.",
            source="rss_feed"
        ),
        RawArticle(
            title="A Survey on Autonomous Agents for Scientific Discovery",
            url="https://example.com/arxiv-scientific-discovery",
            content="Recent advancements in AI have led to the emergence of autonomous agents capable of accelerating scientific discovery. This survey reviews current approaches, highlighting how agents can design experiments, analyze data, and formulate hypotheses independently. Key technologies include reinforcement learning for optimizing experimental protocols and natural language processing for literature review. The potential impact on fields like material science, drug discovery, and climate modeling is immense. However, challenges remain in ensuring reliability, interpretability, and the ability to handle unexpected outcomes.",
            source="arxiv_paper"
        )
    ]

    # Initialize a dummy state with raw articles
    initial_state: AgentState = {
        "raw_articles": dummy_raw_articles,
        "summarized_content": [],
        "newsletter_outline": None,
        "newsletter_draft": None,
        "revision_needed": False,
        "revision_attempts": 0,
    }

    # Run the extraction agent node
    updated_state = extraction_agent_node(initial_state)

    print(f"\nTotal summarized content: {len(updated_state['summarized_content'])}")
    for i, content in enumerate(updated_state['summarized_content']):
        print(f"\n--- Summarized Content {i+1} ---")
        print(f"Original URL: {content.original_url}")
        print(f"Title: {content.title}")
        print(f"Summary ({len(content.summary)} chars): {content.summary}")
        print(f"Key Entities: {', '.join(content.key_entities)}")
        print(f"Trends Identified: {', '.join(content.trends_identified)}")

    if not updated_state['summarized_content']:
        print("\nNo content summarized. Check logs for errors related to LLM or parsing.")