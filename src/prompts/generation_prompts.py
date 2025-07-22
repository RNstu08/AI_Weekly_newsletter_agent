from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime

# Prompt for generating the full newsletter content
# This prompt emphasizes markdown formatting and a professional yet engaging tone.
GENERATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a professional and engaging newsletter writer specializing in AI agent development. "
            "Your task is to transform a structured outline into a complete, well-written, and informative "
            "weekly newsletter. Adopt a clear, concise, and enthusiastic tone. "
            "Ensure accurate information transfer from the provided summaries. "
            "Format the entire newsletter using Markdown syntax. "
            "Include a clear introduction, sections for each category of articles, and a concluding remark. "
            "Use clear headings (e.g., ## Section Title) and bullet points or numbered lists for articles. "
            "Crucially, provide the full markdown content only, with no conversational filler outside the newsletter content."
        ),
        (
            "human",
            "Please generate the weekly AI Agent Development Newsletter based on the following outline. "
            "The current date is {current_date}. Make sure to include this date in the subject line. "
            "Here is the newsletter outline in JSON format:\n\n"
            "```json\n"
            "{newsletter_outline_json}\n" # Expecting a JSON string of NewsletterOutline object
            "```\n\n"
            "Generate the full newsletter content in Markdown format. "
            "Start with the subject line, then the introduction, followed by each section, and finally the conclusion. "
            "For each article, include its title, a concise summary, and a link to the original URL. "
            "**DO NOT include the 'Category' field in the article display.**\n" # <--- NEW INSTRUCTION
            "Example subject line: '# AI Agent Weekly Digest: YYYY-MM-DD Top Trends'\n" # <--- REVISED EXAMPLE (NO 'Subject:')
            "Example article format:\n"
            "### [Article Title](Article URL)\n"
            "- Summary: Article summary\n\n"
            "**Important:** Your output MUST be valid Markdown. Provide ONLY the Markdown content, nothing else. DO NOT include any preamble like 'Here is the generated newsletter content in Markdown format:' or 'Subject:' before the actual subject heading." # <--- STRONGER INSTRUCTION
        ),
    ]
)