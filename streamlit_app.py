import streamlit as st
import io
import sys
import os
from datetime import datetime
import logging
from typing import Optional, Dict, Any, List

# Add the project root to the Python path to allow absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

# Import necessary components from your project
from src.main import create_newsletter_workflow # The function that builds and compiles the graph
from src.state import AgentState # The shared state definition
from src.models.newsletter_models import Newsletter # To display the final output
from src.config import get_settings # Import get_settings
from src.utils import logger as app_logger_instance, setup_logging # Use alias for logger, and get the configured logger instance

# --- Streamlit App Configuration ---
st.set_page_config(
    page_title="AI Agent Newsletter Generator",
    page_icon="🗞️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🗞️ AI Weekly Newsletter Agent")
st.markdown("""
This application demonstrates a **Multi-AI Agent workflow** powered by **LangGraph** and **Open-Source LLMs** to autonomously generate a weekly newsletter about AI agent development.

### Workflow Stages:
1.  **Research:** Gathers relevant articles from web search, RSS feeds, and arXiv.
2.  **Extraction & Summarization:** Extracts key insights, summarizes content, and identifies entities/trends using an LLM.
3.  **Curation & Structuring:** Evaluates relevance, categorizes content, and creates a structured newsletter outline using an LLM.
4.  **Generation:** Drafts the full newsletter content in a beautiful HTML format using an LLM.
5.  **Editorial Review:** Critically assesses the draft for quality and factual accuracy using an LLM-as-a-judge pattern. If needed, requests revisions from the Generation agent.
6.  **Delivery:** Sends the approved newsletter via email and archives it.
""")

# --- Global Logger Setup for Streamlit ---
setup_logging() # Call your utility to set up the default file and console logging for app_logger_instance

# Define the custom StreamlitLogHandler class
class StreamlitLogHandler(logging.Handler):
    def __init__(self, placeholder):
        super().__init__()
        self.placeholder = placeholder
        self.log_messages = []

    def emit(self, record):
        msg = self.format(record)
        self.log_messages.append(f"[{record.levelname}] {msg}")
        st.session_state['streamlit_logs'] = "\n".join(self.log_messages)
        self.placeholder.text(st.session_state['streamlit_logs'])

# --- Define the LangGraph app globally so it's only compiled once per session ---
@st.cache_resource
def get_workflow_app():
    """Caches the LangGraph workflow compilation."""
    app_logger_instance.info("Building and compiling LangGraph workflow (inside cached function)...")
    app = create_newsletter_workflow()
    app_logger_instance.info("LangGraph workflow compiled successfully for Streamlit (inside cached function).")
    return app

# Call the cached function once when the app starts
app = get_workflow_app()


# --- Sidebar for Configuration ---
with st.sidebar:
    st.header("Configuration & Settings")
    settings = get_settings() # Load settings
    
    st.info("These settings are loaded from your `.env` file. For deployment, these would come from Streamlit Secrets.")
    
    st.write(f"**LLM Model:** `{settings.OLLAMA_MODEL_NAME}`")
    
    # --- Allow user to enter recipient email ---
    default_recipients = settings.NEWSLETTER_RECIPIENTS.split(',')[0].strip() if settings.NEWSLETTER_RECIPIENTS else "your_email@example.com"
    st.session_state['user_email_input'] = st.text_input(
        "Recipient Email (for test sends):",
        value=default_recipients,
        help="Enter an email address to send the test newsletter to. Must be verified in SendGrid for production."
    )

    st.write(f"**Sender Email:** `{settings.NEWSLETTER_SENDER_EMAIL}`")
    st.write(f"**Min Quality Score (Approval):** `{settings.EDITORIAL_MIN_QUALITY_SCORE}`")
    st.write(f"**Max Revision Attempts:** `{settings.EDITORIAL_MAX_REVISION_ATTEMPTS}`")
    
    if st.button("Refresh Settings / Clear Cache"):
        st.cache_resource.clear() # Clear cached workflow if settings change fundamentally
        st.rerun() 
    st.markdown("---")
    st.caption("AI Agent News Agent v1.0")


# --- Main App Logic ---
st.header("Generate Newsletter")

# This placeholder will display logs *after* the "Generate" button is clicked
live_log_placeholder = st.empty() 

# Initialize session state for logs and workflow output
if 'streamlit_logs' not in st.session_state:
    st.session_state['streamlit_logs'] = ""
if 'last_workflow_state' not in st.session_state:
    st.session_state['last_workflow_state'] = None # Store the final AgentState

# Display any existing logs from previous runs
live_log_placeholder.text(st.session_state['streamlit_logs'])


if st.button("🚀 Generate Latest Newsletter", type="primary"):
    st.session_state['streamlit_logs'] = "" # Clear logs for new run
    live_log_placeholder.text(st.session_state['streamlit_logs']) # Immediately clear UI logs

    st.info("Starting AI Agent workflow... This may take a few minutes as LLMs process the content.")
    
    # Remove any existing StreamlitLogHandler from previous runs
    for handler in list(app_logger_instance.handlers):
        if isinstance(handler, StreamlitLogHandler):
            app_logger_instance.removeHandler(handler)
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            app_logger_instance.removeHandler(handler)

    # Add a new Streamlit handler for this specific run's output
    run_streamlit_handler = StreamlitLogHandler(live_log_placeholder)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    run_streamlit_handler.setFormatter(formatter)
    app_logger_instance.addHandler(run_streamlit_handler)
    app_logger_instance.setLevel(logging.INFO)

    # Prepare initial state, overriding recipients from user input
    recipients_list = [email.strip() for email in st.session_state['user_email_input'].split(',') if email.strip()]
    if not recipients_list:
        st.error("Please enter at least one valid recipient email address.")
        app_logger_instance.error("No recipient email provided by user.")
        st.stop()
        
    initial_state: AgentState = {
        "raw_articles": [],
        "summarized_content": [],
        "newsletter_outline": None,
        "newsletter_draft": None,
        "revision_needed": False,
        "revision_attempts": 0,
        "newsletter_sent": False,
        "delivery_report": None,
        "recipients": recipients_list, # Pass dynamic recipients via state
    }

    try:
        # Use app.invoke() to get the final state directly after the workflow completes
        # This is more reliable for getting the full, final state.
        final_state_result_from_workflow = app.invoke(initial_state) 
        
        st.session_state['last_workflow_state'] = final_state_result_from_workflow # Persist the final state
        st.success("Workflow completed!")

    except Exception as e:
        app_logger_instance.critical(f"STREAMLIT APP: Critical error during workflow execution: {e}", exc_info=True)
        st.error(f"An unexpected error occurred during workflow execution: {e}. Please check logs for details.")
        st.session_state['last_workflow_state'] = None # Clear state on failure if workflow fails

# --- Display Results from Last Run (Persisted in session_state) ---
# This block runs on every rerun of the script
if st.session_state['last_workflow_state'] is not None:
    final_state_to_display: AgentState = st.session_state['last_workflow_state']
    final_newsletter: Optional[Newsletter] = final_state_to_display.get('newsletter_draft')

    st.subheader("Final Newsletter Status:")
    if final_newsletter: # Check if newsletter_draft exists in the state
        st.write(f"**Subject:** {final_newsletter.subject}")
        st.write(f"**Approved for Delivery:** {final_newsletter.is_approved}")
        st.write(f"**Approval Score:** {final_newsletter.approval_score:.2f}" if final_newsletter.approval_score is not None else "N/A")
        st.write(f"**Feedback:** {final_newsletter.feedback}")
        st.write(f"**Revision Attempts:** {final_newsletter.revision_attempts}")
        st.write(f"**Email Sent Status:** {final_state_to_display.get('newsletter_sent', False)}")
        st.write(f"**Delivery Report:** {final_state_to_display.get('delivery_report', 'N/A')}")
        
        if final_newsletter.is_approved and final_state_to_display.get('newsletter_sent'):
            st.balloons()
            st.success("✨ Newsletter generated, reviewed, and SENT successfully! Check your inbox. ✨")
        elif final_newsletter.is_approved and not final_state_to_display.get('newsletter_sent'):
            st.warning("⚠️ Newsletter approved but email was NOT sent. Check delivery report and logs.")
        else:
            st.error("❌ Newsletter NOT approved for delivery after all attempts.")
        
        st.markdown("---")
        st.subheader("Generated Newsletter Preview:")
        # Render the HTML content for a true preview if content_html is available
        if final_newsletter.content_html:
            st.components.v1.html(final_newsletter.content_html, height=800, scrolling=True)
        else:
            # Fallback to markdown if HTML conversion failed or isn't present
            st.markdown(final_newsletter.content_markdown) 


        st.markdown("---")
        st.subheader("🕵️‍♂️ Agent Workflow Details (Expand to see intermediate steps)")
        
        with st.expander("Raw Articles (Research Agent Output)"):
            raw_articles = final_state_to_display.get('raw_articles', [])
            if raw_articles:
                for i, article in enumerate(raw_articles[:5]): # Show top 5
                    st.markdown(f"**{i+1}. {article.title}**")
                    st.write(f"URL: [{article.url}]({article.url})")
                    st.write(f"Source: {article.source}")
                    st.write(article.content[:200] + "...")
                    st.markdown("---")
            else:
                st.write("No raw articles found or processed.")

        with st.expander("Summarized Content (Extraction Agent Output)"):
            summarized_content = final_state_to_display.get('summarized_content', [])
            if summarized_content:
                for i, content in enumerate(summarized_content[:5]): # Show top 5
                    st.markdown(f"**{i+1}. {content.title}**")
                    st.write(f"Summary: {content.summary[:200]}...")
                    st.write(f"Entities: {', '.join(content.key_entities)}")
                    st.write(f"Trends: {', '.join(content.trends_identified)}")
                    st.markdown("---")
            else:
                st.write("No summarized content generated.")

        with st.expander("Newsletter Outline (Curation Agent Output)"):
            outline = final_state_to_display.get('newsletter_outline')
            if outline:
                st.json(outline.model_dump_json(indent=2)) # Display outline JSON
            else:
                st.write("No newsletter outline generated.")

    else: # This handles the case where newsletter_draft is None even in final_state
        st.error("🚨 Critical Failure: Newsletter draft could not be generated at all. Please check detailed logs.")

st.markdown("---")
st.info("Developed by Ranjith. This demo integrates multiple AI agents (Research, Extraction, Curation, Generation, Editorial, Delivery) into an automated content pipeline.")