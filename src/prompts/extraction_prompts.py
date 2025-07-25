from langchain_core.prompts import ChatPromptTemplate

# Prompt for general summarization and key entity extraction
EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert AI agent development researcher. Your task is to analyze raw articles "
            "and extract the most important information related to AI agent development, multi-agent systems, "
            "and agentic workflows. Focus on new frameworks, research breakthroughs, significant applications, "
            "and emerging concepts. Provide a concise summary (aim for 2-4 sentences) and identify key entities and potential trends."
        ),
        (
            "human",
            "Analyze the following article and provide:\n\n"
            "1. A concise summary (aim for 2-4 sentences, max {max_summary_length} characters) focusing on AI agent relevance.\n"
            "2. A **JSON array of strings** for key entities (e.g., [\"LangGraph\", \"CrewAI\"]).\n" # <--- KEY CHANGE: Emphasize JSON array
            "3. A **JSON array of strings** for any emerging trends or significant implications for the AI agent development field (e.g., [\"autonomous research\", \"ethical AI\"]).\n\n" # <--- KEY CHANGE: Emphasize JSON array
            "Article Title: {title}\n"
            "Article URL: {url}\n"
            "Article Content:\n{content}\n\n"
            "Format your response as a JSON object with the following keys, ensuring **all keys and string values are enclosed in double quotes**: 'summary', 'key_entities', 'trends_identified'.\n"
            "Example:\n"
            "```json\n"
            "{{ \"summary\": \"This is a summary focusing on AI agent relevance, aiming for two to four sentences.\", \"key_entities\": [\"LangGraph\", \"CrewAI\"], \"trends_identified\": [\"autonomous research\"] }}\n"
            "```"
        ),
    ]
)

# Prompt for re-summarization if initial summary is too long (good for robustness)
RESUMMARIZE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert summarizer. Your task is to shorten the given text "
            "to a maximum of {max_summary_length} characters while retaining its core meaning "
            "and relevance to AI agent development.",
        ),
        (
            "human",
            "Shorten the following text:\n\n{text}"
        ),
    ]
)