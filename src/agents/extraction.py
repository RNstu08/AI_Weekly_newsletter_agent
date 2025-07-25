import json
from typing import List, Dict, Any, Optional
import re # Import re for regex operations
import unicodedata # Import unicodedata for advanced string cleaning

from src.config import get_settings
from src.utils import logger, clean_json_string, load_state_from_json, save_state_to_json, DATA_DIR 
from src.tools.llm_interface import get_default_llm
from src.models.research_models import RawArticle, SummarizedContent
from src.prompts.extraction_prompts import EXTRACTION_PROMPT, RESUMMARIZE_PROMPT # Ensure both prompts are imported
from src.state import AgentState # Ensure AgentState is imported

# Load application settings
settings = get_settings()

# Initialize the LLM for this agent
extraction_llm = get_default_llm()

def extraction_agent_node(state: AgentState) -> AgentState:
    """
    Extraction Agent node: Processes raw articles to extract key information and summarize them.
    - Uses an LLM to generate summaries, key entities, and identified trends.
    - Handles re-summarization if the initial summary is too long.
    - Updates the 'summarized_content' field in the state.
    """
    logger.info("---EXTRACTION AGENT: Starting information extraction and summarization---")

    raw_articles: List[RawArticle] = state.get('raw_articles', [])
    if not raw_articles:
        logger.warning("EXTRACTION AGENT: No raw articles found in state. Skipping extraction.")
        new_state = state.copy()
        new_state['summarized_content'] = []
        return new_state

    summarized_content: List[SummarizedContent] = []
    
    # Define LLM specific length limits if different from general summary length
    # This might be used to chunk articles before sending to LLM if they are too long for context window.
    # For now, we'll assume the entire raw_article.content can fit, but this is where
    # MAX_ARTICLE_CHUNK_SIZE would typically be used to break down very long articles.
    max_summary_chars = settings.MAX_SUMMARY_LENGTH
    # max_llm_input_tokens = settings.MAX_ARTICLE_CHUNK_SIZE # Not directly used for simple summary here, but available if content parsing is added

    for i, article in enumerate(raw_articles):
        logger.info(f"EXTRACTION AGENT: Processing article {i+1}/{len(raw_articles)}: {article.title}")
        try:
            # Prepare content for the LLM. If raw_article.content is too large, it needs chunking.
            # For now, we use the snippet/summary from research, which should be short enough.
            article_text_for_llm = article.content if article.content else article.title # Fallback to title if no content/snippet

            # Invoke LLM for initial extraction
            prompt = EXTRACTION_PROMPT.format(
                title=article.title,
                url=article.url,
                content=article_text_for_llm,
                max_summary_length=max_summary_chars
            )
            response_content = extraction_llm.invoke(prompt)

            parsed_llm_output = {}
            try_count = 0
            max_tries = 3

            while try_count < max_tries:
                try:
                    # Use the robust clean_json_string from utils
                    cleaned_json_str = clean_json_string(response_content)
                    
                    # Assert for debugging: ensures the cleaned string actually looks like JSON
                    assert cleaned_json_str.startswith('{') and cleaned_json_str.endswith('}'), \
                        f"Cleaned JSON string does not start/end with braces: {cleaned_json_str[:100]}..."

                    parsed_llm_output = json.loads(cleaned_json_str)
                    break
                except json.JSONDecodeError as e:
                    logger.warning(f"EXTRACTION AGENT: JSONDecodeError for '{article.title}' on try {try_count+1}: {e}. Raw response (cleaned, first 500 chars): '{cleaned_json_str[:500]}...'")
                    try_count += 1
                    if try_count == max_tries:
                        logger.error(f"EXTRACTION AGENT: Max retries reached for JSON parsing for '{article.title}'. Falling back to default summary.")
                        raise # Re-raise after max tries to trigger the outer except
                except ValueError as e: # Catch ValueError from clean_json_string if no braces found
                    logger.error(f"EXTRACTION AGENT: Parsing failed for '{article.title}' due to structural error after cleaning: {e}. Raw response: '{response_content[:500]}...'")
                    raise # Re-raise to trigger the outer except for default handling

            summary = parsed_llm_output.get('summary', 'No summary generated.').strip()
            # Add .rstrip(',') to clean trailing commas from individual string elements
            key_entities = [e.strip().rstrip(',') for e in parsed_llm_output.get('key_entities', []) if isinstance(e, str)]
            trends_identified = [t.strip().rstrip(',') for t in parsed_llm_output.get('trends_identified', []) if isinstance(t, str)]

            # Post-processing: ensure summary length constraints
            if len(summary) > max_summary_chars:
                logger.warning(f"Summary for '{article.title}' is too long ({len(summary)} chars). Re-summarizing.")
                resummarize_prompt = RESUMMARIZE_PROMPT.format(
                    text=summary,
                    max_summary_length=max_summary_chars
                )
                shortened_summary = extraction_llm.invoke(resummarize_prompt).content
                summary = shortened_summary.strip()
                logger.info(f"Summary shortened to {len(summary)} characters.")

            summarized_content.append(
                SummarizedContent(
                    original_url=article.url,
                    title=article.title,
                    summary=summary,
                    key_entities=key_entities,
                    trends_identified=trends_identified
                )
            )
            logger.info(f"EXTRACTION AGENT: Successfully processed '{article.title}'.")
            
        except Exception as e:
            logger.error(f"EXTRACTION AGENT: Failed to process article '{article.title}' due to error: {e}", exc_info=True)
            # Add a placeholder summarized content for failed articles
            summarized_content.append(
                SummarizedContent(
                    original_url=article.url,
                    title=article.title,
                    summary=f"Could not process article due to an error. Original content snippet: {article.content[:max_summary_chars] if article.content else 'N/A'}",
                    key_entities=[],
                    trends_identified=[]
                )
            )

    logger.info("---EXTRACTION AGENT: Completed information extraction and summarization---")

    new_state = state.copy()
    new_state['summarized_content'] = summarized_content
    return new_state

# Example usage (for testing purposes) - This section should be outside the agent node function
if __name__ == "__main__":
    print("--- Testing Extraction Agent Node (Standalone) ---")

    # Try loading raw_articles from file
    loaded_raw_articles_data = load_state_from_json("raw_articles_state.json", DATA_DIR).get('raw_articles', [])
    
    # Reconstruct RawArticle Pydantic objects from loaded dictionaries
    loaded_raw_articles = [RawArticle(**item) for item in loaded_raw_articles_data] if loaded_raw_articles_data else []

    if not loaded_raw_articles:
        print("\nWARNING: No raw_articles_state.json found or it's empty. Using dummy articles for testing.")
        # Create dummy raw articles for testing if file doesn't exist or is empty
        dummy_raw_articles = [
            RawArticle(
                title="LangChain Agents: A Comprehensive Guide",
                url="https://example.com/langchain-agents",
                content="""LangChain has quickly become a cornerstone for building applications with large language models.
                Its agent capabilities allow for dynamic tool use and complex reasoning.
                This guide covers everything from basic agent setup to advanced use cases involving multiple tools and human feedback.
                It details the latest features including streaming outputs and state management for conversational agents.
                The focus is on practical implementation and overcoming common challenges.""",
                source="web_search"
            ),
            RawArticle(
                title="Recent Breakthrough in Multi-Agent Reinforcement Learning",
                url="https://arxiv.org/abs/2401.01234",
                content="""Researchers at ETH Zurich have achieved a significant breakthrough in multi-agent reinforcement learning (MARL) by proposing a novel communication protocol.
                This protocol enables agents to learn optimal collaborative strategies in competitive environments with reduced communication overhead.
                The paper presents benchmarks on complex tasks like multi-robot coordination and traffic control, demonstrating state-of-the-art performance.
                This could revolutionize autonomous systems. Keywords: MARL, communication, robotics, traffic control.""",
                source="arxiv_paper"
            ),
            RawArticle( # Article that might generate a very long summary to test re-summarization
                title="The Future of AI: From General Intelligence to Specialized Agents",
                url="https://example.com/future-ai",
                content="""The discourse around Artificial Intelligence is shifting from generalized AI (AGI) to highly specialized, goal-oriented AI agents.
                These agents, often powered by advanced large language models, are designed to perform specific tasks with high efficiency and autonomy.
                This article delves into the architectural patterns emerging in this field, discussing self-correcting loops,
                tool integration, and the concept of 'agentic workflows'. It also touches upon the ethical implications
                of deploying such autonomous systems at scale, and the regulatory challenges that lie ahead.
                The rapid pace of development suggests a future where AI agents are integrated into almost every facet of industry and daily life,
                requiring robust safety mechanisms and continuous monitoring. This transition will redefine human-AI collaboration.""",
                source="web_search"
            ),
            RawArticle( # Article to trigger JSON parsing error
                title="What are Agentic Workflows? | IBM",
                url="https://www.ibm.com/think/topics/agentic-workflows",
                content="Agentic workflows are AI-driven processes where autonomous AI agents make decisions, take actions and coordinate tasks with minimal human intervention.",
                source="web_search"
            )
        ]
        articles_to_process = dummy_raw_articles
    else:
        print(f"Loaded {len(loaded_raw_articles)} raw articles from file.")
        articles_to_process = loaded_raw_articles


    initial_state: AgentState = {
        "raw_articles": articles_to_process, # Use loaded or dummy articles
        "summarized_content": [], # This will be populated by the agent
        "newsletter_outline": None,
        "newsletter_draft": None,
        "revision_needed": False,
        "revision_attempts": 0,
        "newsletter_sent": False,
        "delivery_report": None,
        "recipients": [] # Not relevant for this node's test, but required by AgentState
    }

    # Run the extraction agent node
    updated_state = extraction_agent_node(initial_state)

    print(f"\nTotal summarized articles: {len(updated_state['summarized_content'])}")
    for i, content in enumerate(updated_state['summarized_content'][:5]): # Display first 5
        print(f"\nSummarized Content {i+1}:")
        print(f"Title: {content.title}")
        print(f"Summary: {content.summary}")
        print(f"Entities: {', '.join(content.key_entities)}")
        print(f"Trends: {', '.join(content.trends_identified)}")

    # --- Save summarized_content for next stage testing ---
    if updated_state['summarized_content']:
        save_state_to_json({"summarized_content": updated_state['summarized_content']}, "summarized_content_state.json", DATA_DIR)
        print(f"\nSaved summarized_content to {DATA_DIR / 'summarized_content_state.json'}")
    else:
        print("\nNo summarized content to save.")