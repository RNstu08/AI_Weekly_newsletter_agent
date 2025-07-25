# AI News Agent: Technical Workflow Deep Dive

This document provides a detailed technical overview of the AI News Agent project, focusing on its architecture, agent interactions, and the underlying technologies.

---

##  **Architecture Overview: LangGraph-Powered Multi-Agent System**

The AI News Agent is built as a **LangGraph state machine**, orchestrating a series of specialized AI agents (nodes) that collectively achieve the complex task of generating a weekly newsletter. The `src/main.py` serves as the central orchestrator, defining the graph, its nodes, and the conditional edges that dictate the flow of information and control between agents.

### **Core Components:**

* **`AgentState` (`src/state.py`):** A `TypedDict` that defines the shared, mutable state passed between LangGraph nodes. This state holds all intermediate data, such as raw articles, summarized content, the newsletter outline, and the draft.
* **Agents (Nodes - `src/agents/`):** Each agent is implemented as a LangGraph node, encapsulating specific business logic and interacting with LLMs or external tools.
* **Tools (`src/tools/`):** Wrappers around external APIs (e.g., SerperDev, arXiv, SendGrid) and internal utilities (e.g., RSS parser, LLM interface) that agents use to perform actions. These are generally LangChain `StructuredTool` instances.
* **Prompts (`src/prompts/`):** Dedicated files for `ChatPromptTemplate` definitions used by different agents. This centralizes prompt management and iteration.
* **Models (`src/models/`):** Pydantic data models for structured data exchange (e.g., `RawArticle`, `SummarizedContent`, `NewsletterOutline`, `Newsletter`). This enforces data integrity and LLM output parsing.
* **Configuration (`src/config.py`):** Uses `pydantic-settings` to manage environment variables and application-wide settings, ensuring secure and flexible configuration.
* **Utilities (`src/utils.py`):** Provides common helper functions, most notably the `logger` for centralized logging and the `clean_json_string` function for robust LLM JSON output parsing.

---

##  **Detailed Workflow & Agent Interactions:**

The workflow is a directed graph where each agent node processes a part of the `AgentState` and passes it along. Conditional edges allow for dynamic branching (e.g., editorial revisions).

### 1. **Research Agent (`src/agents/research.py`)**

* **Input:** Initial empty `AgentState`.
* **Functionality:**
    * Queries `SerperDevTool` (web search) using configurable `RESEARCH_KEYWORDS`.
    * Parses articles from `RSSParserTool` using `RESEARCH_RSS_FEEDS`.
    * Searches `ArxivSearchTool` for academic papers.
    * De-duplicates fetched articles based on URL.
* **Output:** Updates `state['raw_articles']` with a `List[RawArticle]` (Pydantic models).
* **Key Dependencies:** `src.tools.serper_dev`, `src.tools.rss_parser`, `src.tools.arxiv_search`, `src.models.research_models.RawArticle`.

### 2. **Extraction Agent (`src/agents/extraction.py`)**

* **Input:** `AgentState` containing `raw_articles`.
* **Functionality:**
    * Iterates through `raw_articles`.
    * For each article, invokes an LLM (`extraction_llm` via `src.tools.llm_interface.get_default_llm`) with `EXTRACTION_PROMPT` to generate a concise `summary`, `key_entities`, and `trends_identified`.
    * Includes **robust JSON parsing with retry logic**: If the initial `json.loads(clean_json_string(LLM_output))` fails, it attempts a retry after passing the raw LLM output through `src.utils.escape_quotes_in_json_string_values` to fix common LLM errors like unescaped double quotes inside strings.
    * Performs re-summarization via `RESUMMARIZE_PROMPT` if the generated summary exceeds `MAX_SUMMARY_LENGTH`.
* **Output:** Updates `state['summarized_content']` with a `List[SummarizedContent]` (Pydantic models).
* **Key Dependencies:** `src.prompts.extraction_prompts`, `src.tools.llm_interface`, `src.models.research_models.SummarizedContent`, `src.utils.clean_json_string`, `src.utils.escape_quotes_in_json_string_values`.

### 3. **Curation Agent (`src/agents/curation.py`)**

* **Input:** `AgentState` containing `summarized_content`.
* **Functionality:**
    * **Article Scoring:** Invokes LLM (via `curation_llm`) with `CURATION_SCORING_PROMPT` for each `SummarizedContent` to assign a `relevance_score` (0.0-1.0) and a `category` from `NEWSLETTER_CATEGORIES`. Includes JSON parsing retry.
    * Filters articles based on `EDITORIAL_MIN_QUALITY_SCORE`.
    * **Outline Generation:** Invokes LLM again (via `curation_llm`) with `CURATION_OUTLINE_PROMPT` to generate a structured `NewsletterOutline` (including introduction points, sections with articles, conclusion points, and overall trends). This LLM call is also wrapped in robust JSON parsing with retry logic.
    * Includes fallback logic for an empty outline if LLM fails to generate one, ensuring subsequent agents don't break.
* **Output:** Updates `state['newsletter_outline']` with a `NewsletterOutline` (Pydantic model).
* **Key Dependencies:** `src.prompts.curation_prompts`, `src.tools.llm_interface`, `src.models.newsletter_models`, `src.utils.clean_json_string`, `src.utils.escape_quotes_in_json_string_values`.

### 4. **Generation Agent (`src/agents/generation.py`)**

* **Input:** `AgentState` containing `newsletter_outline`.
* **Functionality:**
    * Invokes an LLM (via `generation_llm`) with a *separate, internal `ChatPromptTemplate`* to generate the flowing paragraph text for the `introduction`, `conclusion`, and `overall_trends` based on the points provided in the outline. This call explicitly expects a JSON output for parsing.
    * Programmatically assembles the full newsletter content in Markdown, ensuring consistent heading hierarchy (`## Section`, `### Article Title`), summary format (`- Summary:`), and a single `[Read More](URL)` link per article.
    * Removes any LLM-generated markdown footers to prevent duplication.
    * Converts the final Markdown content to HTML using `markdown` library.
    * Embeds the HTML content into a pre-defined `NEWSLETTER_HTML_TEMPLATE` for a consistent visual style.
* **Output:** Updates `state['newsletter_draft']` with a `Newsletter` object (Pydantic model), including `content_markdown` and `content_html`.
* **Key Dependencies:** `src.prompts.generation_prompts`, `src.tools.llm_interface`, `src.models.newsletter_models`, `markdown`, `premailer`.

### 5. **Editorial Agent (`src/agents/editorial.py`)**

* **Input:** `AgentState` containing `newsletter_draft` and `summarized_content` (for factual verification).
* **Functionality:**
    * Invokes an LLM (as a "judge" via `editorial_llm`) using `EDITORIAL_REVIEW_PROMPT`. The LLM evaluates the `content_markdown` against a defined rubric (factual accuracy, relevance, clarity, tone, formatting).
    * The LLM returns a `quality_score` (0.0-1.0) and `feedback` in JSON format. This parsing also uses `clean_json_string` and the `escape_quotes_in_json_string_values` retry logic.
    * Compares the `quality_score` against `settings.EDITORIAL_MIN_QUALITY_SCORE`.
    * If the score is below threshold and `revision_attempts` are not exhausted, it sets `state['revision_needed'] = True` and increments `revision_attempts`. The LangGraph orchestrator then routes the workflow back to the Generation Agent.
    * If approved or max revisions reached, it sets `state['revision_needed'] = False` and `newsletter_draft.is_approved` accordingly.
* **Output:** Updates `state['newsletter_draft']` (with `is_approved`, `approval_score`, `feedback`, `revision_attempts`), and `state['revision_needed']`, `state['revision_attempts']`.
* **Key Dependencies:** `src.prompts.editorial_prompts`, `src.tools.llm_interface`, `src.models.newsletter_models`, `src.models.research_models.SummarizedContent`, `src.utils.clean_json_string`, `src.utils.escape_quotes_in_json_string_values`.

### 6. **Delivery Agent (`src/agents/delivery.py`)**

* **Input:** `AgentState` containing the final `newsletter_draft`.
* **Functionality:**
    * Checks `newsletter_draft.is_approved`. If `False`, skips delivery.
    * Uses `premailer.transform` to inline all CSS styles directly into the HTML for maximum email client compatibility.
    * Sends the `content_html` via `SendGridAPIClient` to `NEWSLETTER_RECIPIENTS`.
    * Archives both the final Markdown and HTML versions of the newsletter in `data/archives/` for historical records.
* **Output:** Updates `state['newsletter_sent']` and `state['delivery_report']`.
* **Key Dependencies:** `src.tools.sendgrid_client`, `premailer`, `markdown`.

---

##  **Testing & Debugging Strategy:**

The modular design allows for incremental testing:

1.  **Unit/Standalone Node Testing:** Each agent file (`src/agents/*.py`) has an `if __name__ == "__main__":` block that allows running it independently. These blocks are configured to load necessary input state from `data/*.json` files (generated by previous successful steps) and save their own output state for the next agent. This significantly speeds up debugging of individual components.
2.  **Shared Utility Logging:** The `src/utils.py` contains a centralized `logger` and the `clean_json_string` function with extensive `logger.debug` statements, crucial for diagnosing subtle LLM JSON parsing failures.

---
