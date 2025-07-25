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

# Prompt for structuring the newsletter outline (REFINEMENT for POPULATION & CONTENT)
CURATION_OUTLINE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert newsletter editor specializing in AI agent development. "
            "Your goal is to create a compelling and well-structured outline for a weekly newsletter "
            "based on provided summarized articles. Group articles by category. "
            "Identify overarching themes or trends for the introduction and conclusion. "
            "Ensure the newsletter feels comprehensive and valuable."
            "You MUST generate a JSON object that strictly conforms to the `NewsletterOutline` Pydantic model schema. "
            "All top-level fields (introduction_points, sections, conclusion_points, overall_trends) must be included and **MUST be populated with relevant content; do NOT leave lists empty if articles exist that meet the relevance criteria.** "
            "Titles, summaries, and URLs for articles in sections must be **directly extracted from the provided summarized content and placed into their respective fields without modification.**"
            "Ensure categories for articles match one of the `Available Categories` or default to 'Miscellaneous'."
            "Prioritize populating sections with articles that have high relevance. If an article's category is vague, assign it to a logical specific category if possible, or 'Miscellaneous' if no specific fit."
            "DO NOT duplicate articles across sections. Place each article in its *most relevant* single section."
            "Introduction points, conclusion points, and overall trends MUST be informed by the actual article topics provided. Do NOT fabricate or reuse unrelated/generic points. Summarize concisely from the content."
            "If you were provided 3 or more articles in the summarized_articles_json, at least one section in your generated outline MUST contain at least one article. The 'sections' array MUST NOT be empty unless NO articles were selected/provided."
            "Do NOT truncate your output. Ensure that the entire JSON structure is complete and valid, regardless of total length."
            "The URLs in the 'articles' within sections MUST be the exact original URLs provided in the summarized_articles_json. Do NOT put '#' or any other placeholder."
        ),
        (
            "human",
            "Here are the summarized and categorized articles selected for this week's newsletter:\n\n"
            "{summarized_articles_json}\n\n" # Expecting a JSON string of SummarizedContent objects
            "Available Categories: {categories}\n\n" # Passed from Python
            "Please generate a structured outline for the newsletter. Your response MUST be a JSON object "
            "matching the `NewsletterOutline` Pydantic model schema. Populate ALL fields. "
            "The structure is as follows:\n"
            "```json\n"
            "{{ \n"
            "  \"date\": \"YYYY-MM-DDTHH:MM:SS.sssZ\", \n"
            "  \"introduction_points\": [\"Clearly state the main highlights and purpose of this week's digest. Max 3 concise points. Based on articles.\"],\n"
            "  \"sections\": [\n"
            "    {{\n"
            "      \"name\": \"Category Name (from Available Categories, e.g., New Frameworks & Tools)\",\n"
            "      \"articles\": [\n"
            "        {{\n"
            "          \"title\": \"Article Title (exact from provided summarized_articles_json)\",\n"
            "          \"summary\": \"Article summary (exact from provided summarized_articles_json)\",\n"
            "          \"url\": \"Original URL (exact from provided summarized_articles_json) - ABSOLUTELY CRITICAL: DO NOT CHANGE OR OMIT URL\",\n" # <-- STRONGLY EMPHASIZE URL
            "          \"category\": \"Assigned Category (from Available Categories)\"\n"
            "        }}\n"
            "      ] \n"
            "    }}\n"
            "  ],\n"
            "  \"conclusion_points\": [\"Summarize key takeaways and look ahead. Max 2 concise points. Based on articles.\"],\n"
            "  \"overall_trends\": [\"List 2-3 overarching trends from the week's news. Based on articles.\"]\n"
            "}}\n"
            "```\n"
            "Your entire response MUST be only the JSON object, no other text or markdown fences outside it. "
            "**Ensure the 'sections' array contains objects, and each section's 'articles' array contains article objects. These arrays MUST NOT be empty if there are relevant articles to include from the input.**"
            "**Crucial: Only include each selected article ONCE in its MOST relevant section. AVOID DUPLICATES.**"
        ),
    ]
)