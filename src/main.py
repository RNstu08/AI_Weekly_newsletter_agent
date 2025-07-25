from langgraph.graph import StateGraph, END
from datetime import datetime
from typing import Optional
from src.models.newsletter_models import Newsletter

from src.config import get_settings
from src.utils import logger
from src.state import AgentState
from src.agents.research import research_agent_node
from src.agents.extraction import extraction_agent_node
from src.agents.curation import curation_agent_node
from src.agents.generation import generation_agent_node
from src.agents.editorial import editorial_agent_node
from src.agents.delivery import delivery_agent_node

# Load application settings
settings = get_settings()

# --- Define the graph ---
def create_newsletter_workflow():
    """
    Defines and compiles the LangGraph workflow for AI Agent News Agent.
    """
    workflow = StateGraph(AgentState)

    # 1. Add Nodes for each Agent
    workflow.add_node("research", research_agent_node)
    workflow.add_node("extraction", extraction_agent_node)
    workflow.add_node("curation", curation_agent_node)
    workflow.add_node("generation", generation_agent_node)
    workflow.add_node("editorial", editorial_agent_node)
    workflow.add_node("delivery", delivery_agent_node)

    # 2. Set Entry Point: Always start with research for the full pipeline
    workflow.set_entry_point("research")

    # 3. Define Edges (Transitions)
    workflow.add_edge("research", "extraction")
    workflow.add_edge("extraction", "curation")
    workflow.add_edge("curation", "generation")

    # Conditional Edge for Editorial Review (Decision Point!)
    workflow.add_edge("generation", "editorial")

    def should_continue_or_revise(state: AgentState) -> str:
        if state['revision_needed'] and state['revision_attempts'] < settings.EDITORIAL_MAX_REVISION_ATTEMPTS:
            logger.info(f"ORCHESTRATOR: Newsletter needs revision. Rerouting to Generation Agent. Attempt {state['revision_attempts']}.")
            return "revise"
        else:
            if state['newsletter_draft'] and state['newsletter_draft'].is_approved:
                logger.info("ORCHESTRATOR: Newsletter approved. Proceeding to Delivery Agent.")
            else:
                logger.warning("ORCHESTRATOR: Newsletter not approved or max revisions reached. Skipping delivery.")
            return "deliver"

    workflow.add_conditional_edges(
        "editorial",
        should_continue_or_revise,
        {
            "revise": "generation",
            "deliver": "delivery"
        }
    )

    # From Delivery, the workflow ends
    workflow.add_edge("delivery", END)

    # 4. Compile the graph
    app = workflow.compile()
    logger.info("LangGraph workflow compiled successfully.")
    return app

# --- Main execution logic ---
if __name__ == "__main__":
    logger.info("--- Starting AI Agent News Agent Workflow ---")
    
    # Create the workflow graph (will start from research as default)
    app = create_newsletter_workflow()

    # Initial state for the graph for a full run
    initial_state: AgentState = {
        "raw_articles": [],
        "summarized_content": [],
        "newsletter_outline": None,
        "newsletter_draft": None,
        "revision_needed": False,
        "revision_attempts": 0,
        "newsletter_sent": False,
        "delivery_report": None,
        "recipients": settings.get_newsletter_recipients_list(), # Ensure recipients are set in .env
    }

    # Run the workflow
    try:
        final_state = {}
        # The .stream() method yields states at each step
        for s in app.stream(initial_state):
            logger.info(f"ORCHESTRATOR: Current state update: {s}")
            final_state.update(s)

        logger.info("\n--- AI Agent News Agent Workflow Completed ---")
        
        final_newsletter: Optional[Newsletter] = final_state.get('newsletter_draft')

        if final_newsletter:
            print(f"\nFinal Newsletter Subject: {final_newsletter.subject}")
            print(f"Final Newsletter Approved: {final_newsletter.is_approved}")
            print(f"Final Newsletter Approval Score: {final_newsletter.approval_score:.2f}" if final_newsletter.approval_score is not None else "N/A")
            print(f"Final Newsletter Feedback: {final_newsletter.feedback}")
            print(f"Final Newsletter Revision Attempts: {final_newsletter.revision_attempts}")
            print(f"Newsletter Sent Status: {final_state.get('newsletter_sent')}")
            print(f"Delivery Report: {final_state.get('delivery_report')}")
            if final_newsletter.is_approved and final_state.get('newsletter_sent'):
                print("\n**SUCCESS: Weekly newsletter generated, reviewed, and SENT!**")
            elif final_newsletter.is_approved and not final_state.get('newsletter_sent'):
                print("\n**WARNING: Newsletter approved but NOT sent. Check delivery report!**")
            else:
                print("\n**FAILURE: Newsletter NOT approved for delivery.**")
                print("Content:\n", final_newsletter.content_markdown[:500] + "..." if final_newsletter.content_markdown else "No content.")
        else:
            print("\n**CRITICAL FAILURE: Newsletter draft could not be generated at all.**")
            print(f"Final State: {final_state}")

    except Exception as e:
        logger.critical(f"ORCHESTRATOR: Critical error during workflow execution: {e}", exc_info=True)
        print(f"\n**WORKFLOW TERMINATED ABNORMALLY: Check logs for critical errors.**")