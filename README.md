# AI News Agent

## 🗞️ Automated Weekly AI Agent Development Newsletter Generator

This project demonstrates a sophisticated **Multi-AI Agent workflow** powered by **LangGraph** and **Open-Source Large Language Models (LLMs)** to autonomously generate a weekly newsletter focused on the latest advancements in AI agent development, multi-agent systems, and agentic workflows.

It's designed to research, curate, generate, and deliver high-quality, relevant content, showcasing a practical application of autonomous AI agents in content creation.

---

### ✨ **Key Features:**

* **Multi-Agent Architecture:** Leverages LangGraph to orchestrate a team of specialized AI agents, each handling a distinct phase of the newsletter generation pipeline.
* **Comprehensive Research:** Integrates web search (via SerperDev), RSS feed parsing, and academic paper search (via arXiv) to gather diverse and up-to-date information.
* **Intelligent Content Processing:** Agents for extraction, summarization, and content structuring ensure only relevant and concise information makes it to the newsletter.
* **Dynamic Newsletter Generation:** Generates a full newsletter draft in both Markdown and aesthetically pleasing HTML, adapting content based on curated insights.
* **Autonomous Editorial Review:** An LLM-powered editorial agent rigorously evaluates content for quality, factual accuracy, and adherence to guidelines, with built-in revision capabilities.
* **Automated Delivery & Archiving:** Seamlessly sends approved newsletters via SendGrid email service and archives generated content for historical reference.
* **Modular & Extensible:** Designed with clear agent separation, allowing for easy integration of new research sources, LLMs, or delivery mechanisms.
* **Streamlit UI:** Provides an intuitive web interface for triggering the workflow and monitoring real-time logs.

---

### 🚀 **Workflow at a Glance:**

1.  **Research Agent:** Gathers raw articles from diverse sources (Web, RSS, arXiv).
2.  **Extraction Agent:** Summarizes content and identifies key entities/trends.
3.  **Curation Agent:** Scores relevance, categorizes content, and structures the newsletter outline.
4.  **Generation Agent:** Drafts the full newsletter body (intro, sections, conclusion, trends) in Markdown and converts it to HTML.
5.  **Editorial Agent:** Reviews the draft, provides feedback, and determines approval for delivery. If needed, requests revisions from the Generation Agent (up to a set limit).
6.  **Delivery Agent:** Sends the approved newsletter via email and archives it.

*(For a detailed technical deep-dive into each agent and their interactions, please refer to the `TECHNICAL_WORKFLOW.md` file.)*

---

### 💻 **Getting Started (Local Development):**

To run this project locally, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/RNstu08/AI_Weekly_newsletter_agent.git](https://github.com/RNstu08/AI_Weekly_newsletter_agent.git)
    cd AI_Weekly_newsletter_agent # Update directory name if repo name is different from local project folder
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up Environment Variables:**
    Create a `.env` file in the project root (`ai-news-agent/.env`) and add your API keys and configurations. You can use `.env.example` as a template.
    **Remember: Never commit your `.env` file to Git!** It is already included in `.gitignore`.

    ```env
    # .env example
    LLM_PROVIDER=ollama
    OLLAMA_BASE_URL=http://localhost:11434
    OLLAMA_MODEL_NAME=llama3 # Or your preferred model, e.g., "mistral"
    # HF_API_TOKEN=YOUR_HUGGINGFACE_API_TOKEN # Uncomment and set if using HuggingFace
    # HF_MODEL_NAME=google/flan-t5-xxl # Uncomment and set if using HuggingFace

    SERPER_API_KEY=YOUR_SERPER_API_KEY # Get from [https://serper.dev/](https://serper.dev/)
    SENDGRID_API_KEY=YOUR_SENDGRID_API_KEY # Get from [https://sendgrid.com/](https://sendgrid.com/)

    # Ensure sender email is verified in SendGrid
    NEWSLETTER_SENDER_EMAIL=your_sender_email@example.com
    # Comma-separated list of recipient emails
    NEWSLETTER_RECIPIENTS=your_recipient_email@example.com,another_email@example.com 

    # Research Keywords (comma-separated)
    RESEARCH_KEYWORDS="AI agent development, multi-agent systems, agentic workflows, LangChain agents, CrewAI, AutoGen"
    # RSS Feed URLs (comma-separated)
    RESEARCH_RSS_FEEDS="[https://news.ycombinator.com/rss,https://techcrunch.com/feed/,https://rss.arxiv.org/rss/cs](https://news.ycombinator.com/rss,https://techcrunch.com/feed/,https://rss.arxiv.org/rss/cs)"
    RESEARCH_MAX_ARTICLES_PER_RUN=15

    # LLM Context Window Related
    MAX_SUMMARY_LENGTH=500
    MAX_ARTICLE_CHUNK_SIZE=4000 # Adjust based on your LLM's context window

    # Editorial Review Settings
    EDITORIAL_MIN_QUALITY_SCORE=0.75 # Minimum score for approval (0.0 to 1.0)
    EDITORIAL_MAX_REVISION_ATTEMPTS=2 # Max times Generation agent can revise

    # Newsletter Subject Prefix
    NEWSLETTER_SUBJECT_PREFIX="AI Agent Weekly Digest:"
    ```

5.  **Run Ollama (if using Ollama LLM):**
    Ensure Ollama is installed and running on your machine, and you have pulled the model specified in your `.env` (e.g., `ollama run llama3`).

6.  **Run the Full Workflow:**
    ```bash
    python -m src.main
    ```
    This will execute the entire pipeline. Check your configured recipient email for the newsletter!

7.  **Run the Streamlit Web UI:**
    ```bash
    streamlit run src/streamlit_app.py
    ```
    This will open the web interface in your browser, where you can interact with the agent.

---

### 🚀 **Deployment on Streamlit Community Cloud:**

This application is designed for easy deployment on [Streamlit Community Cloud](https://share.streamlit.io/).

1.  **Push your code to GitHub:** Ensure all your latest changes are committed and pushed to a **public GitHub repository**.
2.  **Go to Streamlit Community Cloud:** Log in with your GitHub account.
3.  **Deploy New App:** Click "New app" -> "From existing repository".
4.  **Connect Repository:** Select your `ai-news-agent` repository, specify the branch (`main`), and set the **Main file path** to `src/streamlit_app.py`.
5.  **Configure Secrets:** In "Advanced settings," paste the contents of your local `.env` file (excluding `LLM_PROVIDER` and `OLLAMA_BASE_URL` if you're using Ollama as it needs local setup, but include all API keys and other settings) directly into the "Secrets" text area. Streamlit will securely convert this to `secrets.toml`.
6.  **Deploy!** Watch your app build and deploy. Once live, you'll get a public URL to share.

---

### 🤝 **Contributing:**

Contributions are welcome! Please refer to `TECHNICAL_WORKFLOW.md` for a detailed understanding of the project's architecture and agent interactions.

---