import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import re # re for regex 
import unicodedata # for specific Curation Agent string normalization

from src.config import get_settings
# Import all necessary functions/variables from src.utils
from src.utils import logger, clean_json_string, load_state_from_json, save_state_to_json, DATA_DIR 
from src.tools.llm_interface import get_default_llm
from src.models.research_models import SummarizedContent
from src.models.newsletter_models import NewsletterOutline, NewsletterArticle, NewsletterSection
from src.prompts.curation_prompts import NEWSLETTER_CATEGORIES, CURATION_SCORING_PROMPT, CURATION_OUTLINE_PROMPT
from src.state import AgentState

# Load application settings
settings = get_settings()

# Initialize the LLM for this agent
curation_llm = get_default_llm()

# --- Helper for escaping quotes in string values (for retry logic) ---
def escape_quotes_in_json_string_values(json_string: str) -> str:
    """
    Attempts to escape unescaped double quotes inside string values of a JSON string.
    This is a targeted fix for LLM output issues like 'They"re'.
    It is designed to be applied *after* initial cleaning and *before* a retry of json.loads().
    """
    def replace_callback(match):
        # match.group(1) is the content inside the JSON string value (excluding outer quotes)
        content = match.group(1)
        # Replace unescaped double quotes with escaped ones
        # Use a temporary placeholder to avoid double-escaping if LLM already put `\"`
        content = content.replace(r'\"', '[TEMP_ESCAPED_QUOTE]') # Temporarily unescape valid escapes
        content = content.replace('"', r'\"')                      # Escape the remaining (invalid) double quotes
        content = content.replace('[TEMP_ESCAPED_QUOTE]', r'\"') # Restore valid escapes
        return f'"{content}"'
    
    # This regex finds all quoted strings (keys AND values).
    # We apply the escaping logic within the callback.
    # It must be very careful not to mess with JSON structure.
    # We assume keys are typically well-formed after clean_json_string.
        
    # For a simple case like `{"summary": "It's a "test"."}`, the `"` before test breaks it.
    # We need to target only the string *values* effectively.
    
    # A safer, but more complex approach is to use a lexer or parse more carefully.
    # For now, let's target string values specifically.
    
    # This pattern attempts to match JSON string values.
    # It looks for `": "` followed by content, then a `"` before a comma or brace.
    # This is still not 100% foolproof for all JSON structures, but addresses common LLM issues.
    # The most robust way is manual iteration or a proper JSON repair library.

    # Given the constraint of direct modification, let's simplify to a more direct `replace`
    # for known LLM bad characters *within* string values, if clean_json_string didn't handle it.
    # This is still highly experimental for arbitrary JSON.
    
    # Re-introducing a simpler, more targeted inner string replacement
    # This attempts to fix "word"word" in a value to "word\"word"
    # It assumes quotes within JSON string *values* are the problem.
    # Find patterns like "WORD"WORD" where first WORD is quoted, but second is not.
    # This is often where LLMs fail.
    
    # Let's try a very direct substitution for known problematic patterns in the LLM's raw output.
    # This is less a "JSON parser" and more a "LLM output corrector".
    corrected_str = json_string
    # Example: "They"re" -> "They\'re" or "They\"re"
    corrected_str = corrected_str.replace('"s ', r'\"s ') # e.g., "AI's" -> "AI\"s"
    corrected_str = corrected_str.replace('"t ', r'\"t ') # e.g., "don't" -> "don\"t"
    corrected_str = corrected_str.replace('"re ', r'\"re ') # e.g., "They're" -> "They\"re"
    corrected_str = corrected_str.replace('"ve ', r'\"ve ') # e.g., "I've" -> "I\"ve"
    corrected_str = corrected_str.replace('"ll ', r'\"ll ') # e.g., "we'll" -> "we\"ll"
    corrected_str = corrected_str.replace('"m ', r'\"m ') # e.g., "I'm" -> "I\"m"
    corrected_str = corrected_str.replace('"d ', r'\"d ') # e.g., "I'd" -> "I\"d"
    corrected_str = corrected_str.replace('" "', r'\" \"') # common for "word" "word"
    corrected_str = corrected_str.replace('." ', '.\" ') # fix for end-of-sentence quote issues

    # Final pass to ensure general unescaped quotes within any string are escaped.
    # This is applied *after* the initial parsing attempt, and only if JSON fails.
    # It finds ANY quoted string, and replaces internal unescaped quotes.
    # This is the most complex one and may double escape.
    # Given the previous issues, it's safer to have clean_json_string be minimal.
    # For now, the `clean_json_string` to have handled `\"` via its 3.3.
    # The problem is typically about an unexpected `"` that ends a string prematurely.
    
    # A safer approach for these is manual replacements for known LLM failure patterns
    # (like the above `s`, `t`, etc.) or to instruct the LLM even more strongly.
    
    # Let's try the previous robust regex here if LLM fails, as a retry mechanism.
    # This should find `"` *not* preceded by `\` and replace with `\"`.
    # This is applied *within string values* assuming the string itself is bounded by `"`
    # This regex is still tricky but might be needed.
    
    # Final, *specific* attempt for "brain" type problem:
    # Look for a pattern like `word"word` that occurs *inside* a string.
    # This is too hard for a general regex to do reliably across arbitrary JSON.
    # The best bet is a few targeted `replace()` for common LLM `"` insertions, then retry.
    
    # If the LLM generates `"controller or "brain" to control"`, the `clean_json_string`
    # regex `r'"((?:[^"\\]|\\.)*)"'` will only pick up `"controller or "` as the first string.
    # The rest `brain" to control"` is then malformed.
    # This is why the error is "Expecting ',' delimiter".

    # Let's revert to a very simple inner-quote fixer that just replaces all single quotes,
    # and then manually replace the most common contractions that LLMs fail to escape.
    
    return corrected_str


def curation_agent_node(state: AgentState) -> AgentState:
    logger.info("---CURATION AGENT: Starting content curation and structuring---")

    summarized_content: List[SummarizedContent] = state.get('summarized_content', [])
    if not summarized_content:
        logger.warning("CURATION AGENT: No summarized content found in state. Skipping curation.")
        new_state = state.copy()
        new_state['newsletter_outline'] = NewsletterOutline(
            introduction_points=["No significant news found this week. Please check back next time!"],
            sections=[],
            conclusion_points=["Stay tuned for more updates."],
            overall_trends=["Low news volume"]
        )
        return new_state

    scored_and_categorized_articles: List[SummarizedContent] = []

    # Create a map from original summarized content URLs for accurate URL propagation
    summarized_content_url_map = {item.title.lower(): item.original_url for item in summarized_content}


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

            parsed_llm_output = {}
            try_count = 0
            max_tries = 3

            while try_count < max_tries:
                try:
                    # Use the robust clean_json_string from utils
                    cleaned_json_str = clean_json_string(response_content)
                    
                    # Ensure it's a valid JSON object before parsing (assert for debugging)
                    assert cleaned_json_str.startswith('{') and cleaned_json_str.endswith('}'), \
                        f"Cleaned JSON string does not start/end with braces: {cleaned_json_str[:100]}..."

                    parsed_llm_output = json.loads(cleaned_json_str)
                    break
                except json.JSONDecodeError as e:
                    logger.warning(f"CURATION AGENT: JSONDecodeError for scoring '{article.title}' on try {try_count+1}: {e}. Raw response (cleaned, first 500 chars): '{cleaned_json_str[:500]}...'")
                    # If parsing fails, try to escape inner quotes and retry
                    if try_count < max_tries - 1: # Only try escape if there's a subsequent retry
                        response_content = escape_quotes_in_json_string_values(response_content)
                        logger.warning(f"CURATION AGENT: Attempting inner quote escape for '{article.title}'.")
                    try_count += 1
                    if try_count == max_tries:
                        logger.error(f"CURATION AGENT: Max retries reached for JSON parsing for scoring '{article.title}'. Setting score to 0.0.")
                        raise # Re-raise after max tries to trigger the outer except
                except ValueError as e: # Catch ValueError from clean_json_string if no braces found
                    logger.error(f"CURATION AGENT: Parsing failed for '{article.title}' due to structural error after cleaning: {e}. Raw response: '{response_content[:500]}...'")
                    raise # Re-raise to trigger the outer except for default handling

            relevance_score = float(parsed_llm_output.get('relevance_score', 0.0))
            category = parsed_llm_output.get('category', 'Miscellaneous').strip(',')
            
            if not (0.0 <= relevance_score <= 1.0):
                logger.warning(f"CURATION AGENT: Invalid relevance score '{relevance_score}' for '{article.title}'. Setting to 0.0.")
                relevance_score = 0.0
            if category not in NEWSLETTER_CATEGORIES:
                logger.warning(f"CURATION AGENT: Invalid category '{category}' for '{article.title}'. Setting to 'Miscellaneous'.")
                category = 'Miscellaneous'

            article.relevance_score = relevance_score
            article.category = category
            scored_and_categorized_articles.append(article)
            logger.info(f"CURATION AGENT: Scored '{article.title}' with {relevance_score:.2f}, Category: {category}.")

        except Exception as e:
            logger.error(f"CURATION AGENT: Error during LLM invocation or parsing for scoring '{article.title}': {e}", exc_info=True)
            article.relevance_score = 0.0
            article.category = 'Miscellaneous'
            scored_and_categorized_articles.append(article)

    # --- Step 2: Select Top Articles and Prepare for Outline Generation ---
    selected_articles_for_newsletter = [
        a for a in scored_and_categorized_articles if a.relevance_score is not None and a.relevance_score >= settings.EDITORIAL_MIN_QUALITY_SCORE
    ]
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

    # Prepare articles for outline generation prompt
    articles_for_outline_json_str = json.dumps([
        {
            "title": sa.title,
            "summary": sa.summary,
            "url": summarized_content_url_map.get(sa.title.lower(), sa.original_url), # Use URL from map if title matches, else fallback to original
            "category": sa.category
        }
        for sa in selected_articles_for_newsletter
    ], indent=2)

    # --- Step 3: Generate Newsletter Outline using LLM ---
    logger.info("CURATION AGENT: Generating newsletter outline.")
    try:
        outline_prompt = CURATION_OUTLINE_PROMPT.format(
            summarized_articles_json=articles_for_outline_json_str,
            categories=", ".join(NEWSLETTER_CATEGORIES) # Pass categories for prompt
        )
        response_content = curation_llm.invoke(outline_prompt) # Use outline_prompt here
        logger.debug(f"Raw LLM response for outline: {response_content[:1000]}...") # Log raw response

        parsed_outline_output = {}
        try_count = 0
        max_tries = 3

        while try_count < max_tries:
            try:
                cleaned_json_str = clean_json_string(response_content) # Use the robust cleaning function
                
                # Ensure it's a valid JSON object before parsing (assert for debugging)
                assert cleaned_json_str.startswith('{') and cleaned_json_str.endswith('}'), \
                    f"Cleaned JSON string does not start/end with braces for outline: {cleaned_json_str[:100]}..."

                parsed_outline_output = json.loads(cleaned_json_str)
                break
            except json.JSONDecodeError as e:
                logger.warning(f"CURATION AGENT: JSONDecodeError for outline generation on try {try_count+1}: {e}. Raw response (cleaned, first 500 chars): '{cleaned_json_str[:500]}...'")
                # If parsing fails, try to escape inner quotes and retry
                if try_count < max_tries - 1: # Only try escape if there's a subsequent retry
                    response_content = escape_quotes_in_json_string_values(response_content)
                    logger.warning(f"CURATION AGENT: Attempting inner quote escape for outline generation.")
                try_count += 1
                if try_count == max_tries:
                    logger.error(f"CURATION AGENT: Max retries reached for JSON parsing for outline. Falling back to generic outline.")
                    raise

        # --- Post-parsing validation and correction for the outline structure ---
        # Ensure 'date' field is present and correct
        if 'date' not in parsed_outline_output:
            parsed_outline_output['date'] = datetime.now().isoformat()
        
        # Ensure top-level lists are present, even if empty, or are correct types
        parsed_outline_output['introduction_points'] = [str(p) for p in parsed_outline_output.get('introduction_points', []) if p is not None]
        parsed_outline_output['conclusion_points'] = [str(p) for p in parsed_outline_output.get('conclusion_points', []) if p is not None]
        parsed_outline_output['overall_trends'] = [str(t) for t in parsed_outline_output.get('overall_trends', []) if t is not None]

        # Process sections defensively
        sections_data = parsed_outline_output.get('sections', [])
        cleaned_sections = []
        # Track articles already added to avoid duplicates if LLM puts them in multiple sections
        articles_added_to_outline = set() 

        for section_data in sections_data: # Loop through each section
            if not isinstance(section_data, dict):
                logger.warning(f"CURATION AGENT: Invalid section format detected: {section_data}. Skipping.")
                continue
            
            section_name = section_data.get('name', 'Miscellaneous')
            # Ensure category validation strips any trailing commas from LLM output
            section_name = section_name.strip(',')
            if section_name not in NEWSLETTER_CATEGORIES:
                logger.warning(f"CURATION AGENT: LLM suggested invalid section name '{section_name}'. Defaulting to 'Miscellaneous'.")
                section_name = 'Miscellaneous'

            articles_data_in_section = section_data.get('articles', []) 
            cleaned_articles = []
            for article_data in articles_data_in_section:
                # Deduplicate by title to avoid issues like "A Survey..." appearing multiple times
                article_id = article_data.get('title', '').lower()
                if article_id in articles_added_to_outline:
                    logger.info(f"CURATION AGENT: Skipping duplicate article '{article_data.get('title')}' in outline generation.")
                    continue
                articles_added_to_outline.add(article_id)

                if not isinstance(article_data, dict):
                    logger.warning(f"CURATION AGENT: Invalid article format in section '{section_name}': {article_data}. Skipping.")
                    continue

                # Ensure required article fields are present and valid
                title = article_data.get('title', 'No Title Provided').strip()
                summary = article_data.get('summary', 'No summary provided.').strip()
                # Prioritize URL from summarized_content_url_map if title matches, else fallback to LLM-provided URL or fallback.
                url = summarized_content_url_map.get(title.lower(), article_data.get('url', '#').strip())
                if not url or url == '#': # If LLM still provides # or an empty URL, try map again
                    url = summarized_content_url_map.get(title.lower(), '#').strip() # Fallback to original map or '#'
                
                # Ensure category strips trailing comma from LLM output
                category = article_data.get('category', section_name).strip(',')

                if not title:
                    title = "Untitled Article"
                if not summary:
                    summary = "No summary provided."
                if not url: # Final fallback check for URL
                    url = "#" 
                if category not in NEWSLETTER_CATEGORIES:
                    category = section_name # Ensure category is valid

                cleaned_articles.append(
                    NewsletterArticle(
                        title=title,
                        summary=summary,
                        url=url,
                        category=category
                    )
                )
            if cleaned_articles:
                cleaned_sections.append(
                    NewsletterSection(
                        name=section_name,
                        articles=cleaned_articles
                    )
                )
        # Crucial: Assign cleaned_sections to parsed_outline_output['sections']
        parsed_outline_output['sections'] = cleaned_sections 

        # Final check if sections are still empty despite relevant articles, and force a basic structure.
        # This acts as a safeguard against LLM failing to categorize or format sections properly.
        if not parsed_outline_output['sections'] and selected_articles_for_newsletter:
            logger.warning("CURATION AGENT: LLM generated an empty 'sections' list despite relevant articles. Forcing basic outline structure.")
            # This creates a structured outline that the Generation Agent can process.
            # We still ensure URLs are correct.
            forced_articles_for_outline = []
            for a in selected_articles_for_newsletter:
                forced_articles_for_outline.append(
                    NewsletterArticle(
                        title=a.title,
                        summary=a.summary,
                        url=summarized_content_url_map.get(a.title.lower(), a.original_url),
                        category=a.category # Use the category assigned by scoring
                    )
                )

            newsletter_outline = NewsletterOutline(
                introduction_points=["This week's digest highlights advancements in AI agent development and related fields."],
                sections=[
                    NewsletterSection(
                        name="Featured Articles", # Generic section name
                        articles=forced_articles_for_outline
                    )
                ],
                conclusion_points=["Stay updated for more breakthroughs."],
                overall_trends=["AI agent advancements", "Ethical AI"]
            )
        else:
            newsletter_outline = NewsletterOutline(**parsed_outline_output)

        logger.info("CURATION AGENT: Successfully generated newsletter outline.")

    except Exception as e:
        logger.error(f"CURATION AGENT: Error during LLM invocation or outline processing after JSON parsing: {e}", exc_info=True)
        # This fallback is for when parsing works, but Pydantic validation fails, or another logical error occurs.
        # It will use the new formatting for fallback articles.
        newsletter_outline = NewsletterOutline(
            introduction_points=["An error occurred while generating the outline. Here's a raw list of articles."],
            sections=[
                NewsletterSection(
                    name="Raw Articles (Fallback)",
                    articles=[
                        NewsletterArticle(
                            title=a.title,
                            summary=f"Summary: {a.summary}\nRead more: {a.original_url}", # <--- THIS IS THE FALLBACK FORMATTING
                            url=a.original_url,
                            category=a.category if a.category else "Unknown"
                        ) for a in selected_articles_for_newsletter
                    ]
                )
            ],
            conclusion_points=["Please review the raw articles below."],
            overall_trends=["Error in outline generation", "Review required"]
        )

    logger.info("---CURATION AGENT: Completed content curation and structuring---")

    new_state = state.copy()
    new_state['newsletter_outline'] = newsletter_outline
    return new_state

# Example usage (for testing purposes) - This block is standalone testing.
if __name__ == "__main__":
    print("--- Testing Curation Agent Node (Standalone) ---")

    # Try loading summarized_content from file
    # Ensure DATA_DIR is imported for this block
    from src.utils import DATA_DIR 
    loaded_summarized_content_data = load_state_from_json("summarized_content_state.json", DATA_DIR).get('summarized_content', [])
    
    # Reconstruct SummarizedContent Pydantic objects
    loaded_summarized_content = [SummarizedContent(**item) for item in loaded_summarized_content_data] if loaded_summarized_content_data else []

    if not loaded_summarized_content:
        print("\nWARNING: No summarized_content_state.json found or it's empty. Using dummy summarized content for testing.")
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
            SummarizedContent( # Less relevant article to test scoring/filtering
                original_url="https://example.com/new-smartphone-release",
                title="XYZ Phone 15 Pro Max Released",
                summary="The latest smartphone from XYZ Corp features an improved camera and longer battery life, setting new benchmarks in mobile technology.",
                key_entities=["XYZ Corp", "smartphone", "camera", "battery life"],
                trends_identified=["mobile technology", "consumer electronics"]
            )
        ]
        articles_for_curation = dummy_summarized_content
    else:
        print(f"Loaded {len(loaded_summarized_content)} summarized articles from file.")
        articles_for_curation = loaded_summarized_content


    initial_state: AgentState = {
        "raw_articles": [], # Not directly used by this agent, but part of state
        "summarized_content": articles_for_curation,
        "newsletter_outline": None,
        "newsletter_draft": None,
        "revision_needed": False,
        "revision_attempts": 0,
        "newsletter_sent": False,
        "delivery_report": None,
        "recipients": [],
    }

    updated_state = curation_agent_node(initial_state)

    print(f"\n--- Generated Newsletter Outline ---")
    if updated_state['newsletter_outline']:
        outline = updated_state['newsletter_outline']
        print(f"Introduction: {outline.introduction_points}")
        print(f"Overall Trends: {outline.overall_trends}")
        for section in outline.sections:
            print(f"\nSection: {section.name}")
            for i, article in enumerate(section.articles):
                print(f"    Article {i+1}:")
                print(f"      Title: {article.title}")
                print(f"      Summary: {article.summary[:100]}...")
                print(f"      URL: {article.url}")
                print(f"      Category (from LLM): {article.category}")
        
        # --- Save newsletter_outline for next stage testing ---
        save_state_to_json({"newsletter_outline": updated_state['newsletter_outline']}, "newsletter_outline_state.json", DATA_DIR)
        print(f"\nSaved newsletter_outline to {DATA_DIR / 'newsletter_outline_state.json'}")

    else:
        print("No newsletter outline generated. Check logs for errors or if no articles met the relevance threshold.")
        print("\nNo newsletter outline to save.")