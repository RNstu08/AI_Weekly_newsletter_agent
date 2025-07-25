from langchain_core.prompts import ChatPromptTemplate

# Rubric/Criteria for the Editorial Agent to evaluate against
EDITORIAL_RUBRIC = """
Evaluate the provided newsletter draft based on the following criteria.
Provide a 'quality_score' (float from 0.0 to 1.0) and detailed 'feedback' (string) if the score is below acceptable,
or 'Approved' if the score is sufficient.

## Evaluation Criteria:

1.  **Factual Accuracy (Weight: 0.3):**
    * Is all information presented factually correct according to the original summarized content?
    * Are there any hallucinations (fabricated information)?
    * Are URLs correctly formatted and present?

2.  **Relevance & Focus (Weight: 0.25):**
    * Does the newsletter stay focused on "AI agent development, multi-agent systems, and agentic workflows"?
    * Are all included articles highly relevant to the core topic?
    * Is less relevant content appropriately filtered or minimized?

3.  **Clarity & Conciseness (Weight: 0.2):**
    * Is the language clear, precise, and easy to understand?
    * Are summaries truly concise and to the point (within specified length, where applicable)?
    * Is there any repetitive phrasing or unnecessary verbosity?

4.  **Tone & Engagement (Weight: 0.15):**
    * Is the tone professional, informative, and engaging?
    * Does it avoid overly casual or overly academic language where inappropriate?
    * Does the introduction hook the reader and the conclusion provide a good wrap-up?

5.  **Formatting & Structure (Weight: 0.1):**
    * Does it adhere to Markdown formatting guidelines (headings, bullet points, links)?
    * Is the overall structure logical and easy to navigate (intro, sections, conclusion)?
    * Are headings clear and consistent?

## Instructions for Output:

Provide a JSON object with the following structure:
```json
{{ # <--- DOUBLED CURLY BRACE HERE
  "quality_score": <float, 0.0 to 1.0>,
  "is_approved": <bool>,
  "feedback": "<string, detailed feedback if not approved, or 'Approved' if approved>",
  "issues_found": [
    {{"type": "Factual Accuracy", "description": "Specific issue details"}}, # <--- DOUBLED CURLY BRACES HERE
    {{"type": "Clarity", "description": "Specific issue details"}} # <--- DOUBLED CURLY BRACES HERE
  ]
}} # <--- DOUBLED CURLY BRACE HERE
"""

#The main prompt for the Editorial Agent to review the newsletter draft
EDITORIAL_REVIEW_PROMPT = ChatPromptTemplate.from_messages(
[
    (
        "system",
        "You are an impartial, highly analytical editor and quality assurance specialist for an AI agent development newsletter. "
        "Your primary role is to rigorously review a given newsletter draft against a set of quality criteria and provide objective feedback in JSON format. "
        "Your output MUST be a JSON object conforming exactly to the specified schema, and NOTHING else. "
        "If the overall 'quality_score' meets or exceeds the threshold (e.g., 0.7), set 'is_approved' to true and 'feedback' to 'Approved'. Otherwise, 'is_approved' should be false and 'feedback' must contain detailed, actionable advice for improvement."
        # Pass the rubric here. Note the f-string syntax in a message tuple.
        # EDITORIAL_RUBRIC already contains the doubled braces, so it's safe to inject.
        f"\n\nHere is the rubric and instructions for your evaluation:\n\n\n{EDITORIAL_RUBRIC}\n\n\n"
    ),
    (
        "human",
        "Please review the following newsletter draft. Focus on applying the rubric strictly:\n\n"
        "```markdown\n" # <-- This ` is crucial for the markdown block
        "Subject: {subject}\n\n" # Note: Two newlines after subject is typical for markdown heading/first paragraph separation
        "{content_markdown}\n"
        "```\n\n" # <-- This ` is crucial for closing the markdown block

        "Here are the summarized original articles for factual verification (JSON format). You MUST use this information to verify factual accuracy:\n\n"
        "```json\n" # <-- This ` is crucial for the JSON block
        "{summarized_articles_json}\n"
        "```\n\n" # <-- This ` is crucial for closing the JSON block

        "**Based on the rubric, critically evaluate the newsletter draft. Provide ONLY the JSON output, and ensure the 'feedback' field accurately reflects the 'is_approved' status.**"
    ),
]
)