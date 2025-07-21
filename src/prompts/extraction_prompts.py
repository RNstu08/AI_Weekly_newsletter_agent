from langchain_core.prompts import ChatPromptTemplate

# Prompt for general summarization and key entity extraction
EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert AI agent development researcher. Your task is to analyze raw articles "
            "and extract the most important information related to AI agent development, multi-agent systems, "
            "and agentic workflows. Focus on new frameworks, research breakthroughs, significant applications, "
            "and emerging concepts. Provide a concise summary and identify key entities and potential trends.",
        ),
        (
            "human",
            "Analyze the following article and provide:\n\n"
            "1. A concise summary (max {max_summary_length} characters) focusing on AI agent relevance.\n"
            "2. A comma-separated list of key entities (e.g., specific agent names, framework names, companies, researchers, project names).\n"
            "3. Any emerging trends or significant implications for the AI agent development field.\n\n"
            "Article Title: {title}\n"
            "Article URL: {url}\n"
            "Article Content:\n{content}\n\n"
            "Format your response as a JSON object with the following keys: 'summary', 'key_entities', 'trends_identified'.\n"
            "Example:\n"
            "```json\n"
            "{{ \"summary\": \"...\", \"key_entities\": [\"LangGraph\", \"CrewAI\"], \"trends_identified\": [\"autonomous research\"] }}\n"
            "```"
        ),
    ]
)

# Prompt for re-summarization if initial summary is too long (optional, but good for robustness)
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