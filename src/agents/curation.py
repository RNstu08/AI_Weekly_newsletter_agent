import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

from src.config import get_settings
from src.utils import logger
from src.tools.llm_interface import get_default_llm # Our LLM interface
from src.models.research_models import SummarizedContent
from src.models.newsletter_models import NewsletterOutline, NewsletterArticle, NewsletterSection # New models
from src.prompts.curation_prompts import NEWSLETTER_CATEGORIES, CURATION_SCORING_PROMPT, CURATION_OUTLINE_PROMPT
from src.state import AgentState # Our shared state definition

# Load application settings
settings = get_settings()

# Initialize the LLM for this agent
curation_llm = get_default_llm()

def curation_agent_node(state: AgentState) -> AgentState:
    """
    Curation Agent node: Evaluates summarized content, selects top articles,
    categorizes them, and generates a structured newsletter outline.
    - Iterates through 'summarized_content' to score relevance and assign categories.
    - Selects articles above a certain relevance threshold.
    - Uses LLM to create the final NewsletterOutline.
    - Updates the 'newsletter_outline' field in the state.
    """
    logger.info("---CURATION AGENT: Starting content curation and structuring---")

    summarized_content: List[SummarizedContent] = state.get('summarized_content', [])
    if not summarized_content:
        logger.warning("CURATION AGENT: No summarized content found in state. Skipping curation.")
        new_state = state.copy()
        new_state['newsletter_outline'] = None # Ensure it's explicitly None
        return new_state

    scored_and_categorized_articles: List[SummarizedContent] = []

    # --- Step 1: Score Relevance and Assign Category for Each Article ---
    logger.info(f"CURATION AGENT: Scoring and categorizing {len(summarized_content)} articles.")
    for i, article in enumerate(summarized_content):
        logger.info(f"CURATION AGENT: Scoring article {i+1}/{len(summarized_content)}: {article.title}")
        try:
            prompt = CURATION_SCORING_PROMPT.format(
                title=article.title,
                summary=article.summary,
                key_entities=", ".join(article.key_entities),
                trends_identified=", ".join(article.trends_identified),
                categories=", ".join(NEWSLETTER_CATEGORIES)
            )
            response_content = curation_llm.invoke(prompt)

            # Robust JSON parsing from LLM response
            json_str = ""
            try:
                # Regex to find JSON wrapped in ```json ... ``` or just { ... }
                match = re.search(r"```json\s*(\{.*?\})\s*```|(\{.*?\})", response_content, re.DOTALL)
                if match:
                    json_str = match.group(1) if match.group(1) else match.group(2)
                if not json_str:
                    start_brace = response_content.find('{')
                    end_brace = response_content.rfind('}')
                    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                        json_str = response_content[start_brace : end_brace + 1]
                    else:
                        raise ValueError("No discernible JSON string found in LLM response for scoring.")

                parsed_llm_output = json.loads(json_str)
                relevance_score = float(parsed_llm_output.get('relevance_score', 0.0))
                category = parsed_llm_output.get('category', 'Miscellaneous')

                # Basic validation for score and category
                if not (0.0 <= relevance_score <= 1.0):
                    logger.warning(f"CURATION AGENT: Invalid relevance score '{relevance_score}' for '{article.title}'. Setting to 0.0.")
                    relevance_score = 0.0
                if category not in NEWSLETTER_CATEGORIES:
                    logger.warning(f"CURATION AGENT: Invalid category '{category}' for '{article.title}'. Setting to 'Miscellaneous'.")
                    category = 'Miscellaneous'

                # Update the SummarizedContent object with score and category
                article.relevance_score = relevance_score
                article.category = category
                scored_and_categorized_articles.append(article)
                logger.info(f"CURATION AGENT: Scored '{article.title}' with {relevance_score:.2f}, Category: {category}.")

            except (json.JSONDecodeError, ValueError) as parse_e:
                logger.error(f"CURATION AGENT: Failed to parse JSON for scoring '{article.title}': {parse_e}. Raw response: '{response_content[:500]}...'")
                article.relevance_score = 0.0 # Assign low score if parsing fails
                article.category = 'Miscellaneous'
                scored_and_categorized_articles.append(article) # Still add to list
            except Exception as e:
                logger.error(f"CURATION AGENT: Unexpected error during scoring '{article.title}': {e}", exc_info=True)
                article.relevance_score = 0.0
                article.category = 'Miscellaneous'
                scored_and_categorized_articles.append(article)

        except Exception as e:
            logger.error(f"CURATION AGENT: Error during LLM invocation for scoring '{article.title}': {e}", exc_info=True)
            article.relevance_score = 0.0 # Assign low score if LLM call fails
            article.category = 'Miscellaneous'
            scored_and_categorized_articles.append(article)

    # --- Step 2: Select Top Articles and Prepare for Outline Generation ---
    # Filter articles by a minimum relevance score
    selected_articles_for_newsletter = [
        a for a in scored_and_categorized_articles if a.relevance_score >= settings.EDITORIAL_MIN_QUALITY_SCORE # Using this threshold
    ]
    # Sort by relevance descending, then by title for consistency
    selected_articles_for_newsletter.sort(key=lambda x: (x.relevance_score if x.relevance_score is not None else 0.0), reverse=True)

    if not selected_articles_for_newsletter:
        logger.warning("CURATION AGENT: No articles met the minimum relevance threshold. Newsletter will be empty.")
        new_state = state.copy()
        new_state['newsletter_outline'] = NewsletterOutline(
            introduction_points=["No significant news found this week. Please check back next time!"],
            sections=[],
            conclusion_points=["Stay tuned for more updates."],
            overall_trends=["Low news volume"]
        )
        return new_state

    logger.info(f"CURATION AGENT: Selected {len(selected_articles_for_newsletter)} articles for the newsletter.")

    # Convert selected SummarizedContent to a format suitable for the outline prompt (JSON string)
    # This also maps to NewsletterArticle structure for the LLM
    articles_for_outline_json_str = json.dumps([
        {
            "title": sa.title,
            "summary": sa.summary,
            "url": sa.original_url,
            "category": sa.category
        }
        for sa in selected_articles_for_newsletter
    ], indent=2)

    # --- Step 3: Generate Newsletter Outline using LLM ---
    logger.info("CURATION AGENT: Generating newsletter outline.")
    try:
        outline_prompt = CURATION_OUTLINE_PROMPT.format(
            summarized_articles_json=articles_for_outline_json_str
        )
        response_content = curation_llm.invoke(outline_prompt)
        
        # Robust JSON parsing for the outline
        json_str = ""
        try:
            match = re.search(r"```json\s*(\{.*?\})\s*```|(\{.*?\})", response_content, re.DOTALL)
            if match:
                json_str = match.group(1) if match.group(1) else match.group(2)
            if not json_str:
                start_brace = response_content.find('{')
                end_brace = response_content.rfind('}')
                if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                    json_str = response_content[start_brace : end_brace + 1]
                else:
                    raise ValueError("No discernible JSON string found in LLM response for outline.")

            parsed_outline_output = json.loads(json_str)
            
            # Use Pydantic to validate and create the NewsletterOutline
            # This will also validate nested NewsletterSection and NewsletterArticle structures
            newsletter_outline = NewsletterOutline(**parsed_outline_output)
            logger.info("CURATION AGENT: Successfully generated newsletter outline.")

        except (json.JSONDecodeError, ValueError) as parse_e:
            logger.error(f"CURATION AGENT: Failed to parse JSON for newsletter outline: {parse_e}. Raw response: '{response_content[:500]}...'")
            # Fallback to a minimal, generic outline
            newsletter_outline = NewsletterOutline(
                introduction_points=["An error occurred while generating the outline. Here's a raw list of articles."],
                sections=[
                    NewsletterSection(
                        name="Raw Articles",
                        articles=[
                            NewsletterArticle(
                                title=a.title,
                                summary=a.summary,
                                url=a.original_url,
                                category=a.category if a.category else "Unknown"
                            ) for a in selected_articles_for_newsletter
                        ]
                    )
                ],
                conclusion_points=["Please review the raw articles below."],
                overall_trends=["Error in outline generation"]
            )
        except Exception as e:
            logger.error(f"CURATION AGENT: Unexpected error during outline parsing: {e}", exc_info=True)
            newsletter_outline = NewsletterOutline(
                introduction_points=["An unexpected error occurred while generating the outline."],
                sections=[],
                conclusion_points=[],
                overall_trends=[]
            )
    except Exception as e:
        logger.error(f"CURATION AGENT: Error during LLM invocation for outline generation: {e}", exc_info=True)
        # Fallback if the LLM invocation itself fails (e.g., API error, network issue)
        newsletter_outline = NewsletterOutline(
            introduction_points=["A critical error occurred while generating the newsletter outline. Please check system logs."],
            sections=[],
            conclusion_points=[],
            overall_trends=["Critical outline generation failure"]
        )

    logger.info("---CURATION AGENT: Completed content curation and structuring---")

    # Update the state with the newsletter outline
    new_state = state.copy()
    new_state['newsletter_outline'] = newsletter_outline
    return new_state


# Example usage (for testing purposes)
if __name__ == "__main__":
    print("--- Testing Curation Agent Node (Standalone) ---")

    # Create dummy summarized content for testing
    dummy_summarized_content = [
        SummarizedContent(
            original_url="https://example.com/langgraph-new-features",
            title="LangGraph New Features: Cycles and Memory",
            summary="LangGraph introduces explicit cycles and memory management, enabling complex multi-agent conversations and long-term context retention.",
            key_entities=["LangGraph", "memory management", "multi-agent conversations"],
            trends_identified=["autonomous AI", "continuous learning", "adaptability"]
        ),
        SummarizedContent(
            original_url="https://example.com/ai-ethics-multi-agent",
            title="AI Ethics in Multi-Agent Systems",
            summary="Embedding ethics into multi-agent systems for fairness, transparency, and accountability in autonomous decision-making.",
            key_entities=["multi-agent systems", "AI ethics", "moral reasoning"],
            trends_identified=["ethical AI", "autonomous decision-making"]
        ),
        SummarizedContent(
            original_url="https://example.com/arxiv-scientific-discovery",
            title="A Survey on Autonomous Agents for Scientific Discovery",
            summary="Autonomous agents accelerate scientific discovery through experiment design, data analysis, and hypothesis formulation using reinforcement learning and natural language processing.",
            key_entities=["autonomous agents", "scientific discovery", "reinforcement learning", "natural language processing"],
            trends_identified=["autonomous research", "scientific automation"]
        ),
        SummarizedContent(
            original_url="https://example.com/new-ollama-models",
            title="Ollama Adds New Llama 3 and Mistral Variants",
            summary="Ollama expands its model library with new versions of Llama 3 and Mistral, offering improved performance and smaller sizes for local development.",
            key_entities=["Ollama", "Llama 3", "Mistral", "local LLMs"],
            trends_identified=["local AI deployment", "efficient LLMs"]
        ),
        SummarizedContent(
            original_url="https://example.com/ai-job-market-trends",
            title="AI Job Market Sees Surge in Agent Developer Roles",
            summary="Demand for AI agent developers is rapidly increasing, reflecting a shift towards more specialized and autonomous AI applications in the industry.",
            key_entities=["AI agent developer", "job market", "AI applications"],
            trends_identified=["specialized AI roles", "industry adoption of agents"]
        ),
        SummarizedContent( # Less relevant article to test filtering
            original_url="https://example.com/new-smartphone-release",
            title="XYZ Phone 15 Pro Max Released",
            summary="The latest smartphone from XYZ Corp features an improved camera and longer battery life, setting new benchmarks in mobile technology.",
            key_entities=["XYZ Corp", "smartphone", "camera", "battery life"],
            trends_identified=["mobile technology", "consumer electronics"]
        )
    ]

    # Initialize a dummy state with summarized content
    initial_state: AgentState = {
        "raw_articles": [], # Not directly used by this agent, but part of state
        "summarized_content": dummy_summarized_content,
        "newsletter_outline": None,
        "newsletter_draft": None,
        "revision_needed": False,
        "revision_attempts": 0,
    }

    # Run the curation agent node
    updated_state = curation_agent_node(initial_state)

    print(f"\n--- Generated Newsletter Outline ---")
    if updated_state['newsletter_outline']:
        print(f"Introduction: {updated_state['newsletter_outline'].introduction_points}")
        print(f"Overall Trends: {updated_state['newsletter_outline'].overall_trends}")
        for section in updated_state['newsletter_outline'].sections:
            print(f"\nSection: {section.name}")
            for i, article in enumerate(section.articles):
                print(f"  Article {i+1}:")
                print(f"    Title: {article.title}")
                print(f"    Summary: {article.summary[:100]}...")
                print(f"    URL: {article.url}")
                print(f"    Category (from LLM): {article.category}")
    else:
        print("No newsletter outline generated.")
        print("Please check logs for errors or if no articles met the relevance threshold.")