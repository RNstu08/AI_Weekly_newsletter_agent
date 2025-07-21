from langchain_core.prompts import ChatPromptTemplate

# Define categories for the newsletter
NEWSLETTER_CATEGORIES = [
    "Top Insights & Breakthroughs",
    "New Frameworks & Tools",
    "Agentic Workflow Spotlights",
    "Ethical & Societal Impact",
    "Research & Academic Highlights",
    "Tutorials & Learning Resources",
    "Industry News & Applications",
    "Miscellaneous"
]

# Prompt for scoring relevance and assigning category
CURATION_SCORING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert AI agent development editor. Your task is to evaluate a summarized article "
            "for its relevance to a weekly newsletter on AI agent development, multi-agent systems, "
            "and agentic workflows. Assign a relevance score from 0.0 (not relevant) to 1.0 (highly relevant). "
            "Also, assign it to the most appropriate newsletter category from the provided list. "
            "Prioritize content that is novel, impactful, or highly practical for AI agent developers. "
            "If the article is not clearly relevant, assign a low score (e.g., 0.2 or less)."
        ),
        (
            "human",
            "Evaluate the following summarized article:\n\n"
            "Title: {title}\n"
            "Summary: {summary}\n"
            "Key Entities: {key_entities}\n"
            "Trends Identified: {trends_identified}\n\n"
            "Available Categories: {categories}\n\n"
            "Format your response as a JSON object with the following keys: 'relevance_score' (float), 'category' (string)."
            "Example:\n"
            "```json\n"
            "{{ \"relevance_score\": 0.85, \"category\": \"New Frameworks & Tools\" }}\n"
            "```"
        ),
    ]
)

# Prompt for structuring the newsletter outline
CURATION_OUTLINE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert newsletter editor specializing in AI agent development. "
            "Your goal is to create a compelling and well-structured outline for a weekly newsletter "
            "based on provided summarized articles. Group articles by category. "
            "Identify overarching themes or trends for the introduction and conclusion. "
            "Ensure the newsletter feels comprehensive and valuable."
        ),
        (
            "human",
            "Here are the summarized and categorized articles selected for this week's newsletter:\n\n"
            "{summarized_articles_json}\n\n" # Expecting a JSON string of SummarizedContent objects
            "Please generate a structured outline for the newsletter. Include:\n"
            "1. An introduction with 2-3 key points/highlights for the week.\n"
            "2. Sections for each category that has articles, with clear headings and a list of articles for each (title, summary, URL).\n"
            "3. A conclusion with 1-2 key takeaways or forward-looking statements.\n"
            "4. A list of overall emerging trends from the week's news.\n\n"
            "Format your response as a JSON object matching the `NewsletterOutline` Pydantic model schema. "
            "Example of expected structure (omit articles content for brevity, just show the structure):\n"
            "```json\n"
            "{{ \"introduction_points\": [\"...\"], \"sections\": [{{ \"name\": \"Category Name\", \"articles\": [{{ \"title\": \"...\", \"summary\": \"...\", \"url\": \"...\", \"category\": \"...\"}}]}}], \"conclusion_points\": [\"...\"], \"overall_trends\": [\"...\"] }}\n"
            "```"
        ),
    ]
)