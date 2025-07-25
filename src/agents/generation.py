import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import markdown
from premailer import transform

from langchain_core.prompts import ChatPromptTemplate 

from src.config import get_settings
from src.utils import logger, clean_json_string, load_state_from_json, save_state_to_json, DATA_DIR 
from src.tools.llm_interface import get_default_llm
from src.models.newsletter_models import NewsletterOutline, Newsletter, NewsletterSection, NewsletterArticle
from src.prompts.generation_prompts import GENERATION_PROMPT, NEWSLETTER_FOOTER 
from src.state import AgentState

settings = get_settings()
generation_llm = get_default_llm()

# --- HTML Template for the Newsletter ---
NEWSLETTER_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
    <style type="text/css"> /* Explicit type for email compatibility */
        /* Basic Reset */
        body, html {{ margin: 0; padding: 0; }}

        /* Container & Body Styles */
        body {{
            font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif; /* Added common fallbacks */
            line-height: 1.6;
            color: #333333; /* Darker grey for better contrast */
            background-color: #f4f4f4; /* Light grey background for the email canvas */
            -webkit-text-size-adjust: 100%; /* Prevent font scaling on iOS */
            -ms-text-size-adjust: 100%; /* Prevent font scaling on Windows Mobile */
        }}
        .header-section {{
            background-color: #2980b9; /* Dark blue background for header */
            color: #ffffff; /* White text */
            padding: 20px 0;
            text-align: center;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            margin-bottom: 20px;
        }}
        .header-section h1 {{
            color: #ffffff;
            font-size: 2.5em;
            margin: 0;
            padding: 0;
            border-bottom: none;
        }}
        .header-section .date-info {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .container {{
            max-width: 700px;
            margin: 0px auto 20px auto; /* Adjusted margin to fit header */
            background: #ffffff; /* White background for the content area */
            padding: 0px 30px 30px 30px; /* Adjusted padding, top padding handled by header */
            border-bottom-left-radius: 12px; /* Rounded corners only at bottom */
            border-bottom-right-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1); /* Subtle shadow */
            border: 1px solid #e0e0e0; /* Light border */
            border-top: none; /* No top border, connects to header */
        }}
        /* Headings */
        h1, h2, h3, h4, h5, h6 {{
            color: #2c3e50; /* Dark blue-grey for headings */
            margin-top: 1.5em;
            margin-bottom: 0.8em;
            line-height: 1.2;
        }}
        /* Primary H1 for the main content block, distinct from header H1 */
        .container h1 {{
            font-size: 2.2em;
            color: #2980b9; /* A vibrant blue for main titles */
            text-align: center;
            margin-bottom: 1em;
            padding-bottom: 0.5em; /* Add padding for separator effect */
            border-bottom: 1px solid #dddddd; /* Subtle line below main title */
        }}
        h2 {{
            font-size: 1.8em;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 0.5em;
            color: #34495e; /* Slightly darker blue-grey for section titles */
        }}
        h3 {{
            font-size: 1.4em;
            color: #3498db; /* A lighter blue for article titles */
        }}
        /* Paragraphs & Lists */
        p {{
            margin-bottom: 1em;
        }}
        ul {{
            list-style-type: disc;
            margin-left: 20px;
            margin-bottom: 1em;
        }}
        li {{
            margin-bottom: 0.5em;
        }}
        /* Links */
        a {{
            color: #3498db; /* Consistent blue for links */
            text-decoration: none;
            font-weight: bold;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        /* Footer */
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            text-align: center;
            font-size: 0.9em;
            color: #7f8c8d; /* Muted grey for footer text */
        }}
        .section-separator {{
            border-bottom: 1px dashed #cccccc; /* Dashed separator for sections */
            margin: 2em 0;
        }}
        .read-more-link {{
            display: block; /* Make it a block element to go to a new line */
            margin-top: 0.5em; /* Space it out from the summary */
            font-size: 0.9em;
            text-align: right; /* Align to the right for a clean look */
        }}
        /* Responsive adjustments for simple email clients - use minimal media queries */
        @media (max-width: 600px) {{
            .container {{
                margin: 10px auto;
                padding: 15px;
            }}
            h1 {{ font-size: 1.8em; }}
            h2 {{ font-size: 1.5em; }}
            h3 {{ font-size: 1.2em; }}
        }}
    </style>
</head>
<body>
    <div class="header-section">
        <h1>The AI Agent Weekly Digest</h1>
        <p class="date-info">{current_date_header}</p>
    </div>
    <div class="container">
        {content_html_body}
    </div>
    <div class="footer">
        <p>This newsletter is generated by an AI Agent. | &copy; {current_year} AI Agent News</p>
        <p>Stay updated on the latest in AI Agent Development!</p>
    </div>
</body>
</html>
"""


def generation_agent_node(state: AgentState) -> AgentState:
    logger.info("---GENERATION AGENT: Starting newsletter content generation---")
    newsletter_outline: Optional[NewsletterOutline] = state.get('newsletter_outline')
    
    current_date_formatted_for_subject = datetime.now().strftime('%Y-%m-%d')
    current_date_formatted_for_header = datetime.now().strftime('%B %d, %Y')
    current_year = datetime.now().year
    generated_subject = f"{settings.NEWSLETTER_SUBJECT_PREFIX} {current_date_formatted_for_subject}" # Default subject


    # --- Check for Curation Agent's Outline Validity ---
    if not newsletter_outline or not newsletter_outline.sections: 
        logger.warning("GENERATION AGENT: No proper newsletter outline (sections empty) found. Generating basic fallback markdown.")
        
        fallback_markdown_content_parts = []
        fallback_markdown_content_parts.append(f"## Introduction\n\nThis week's digest highlights important developments in AI agent technology. An error occurred while generating the detailed outline, so here's a raw list of articles from last stage's processing.\n\n")

        summarized_content_from_state = state.get('summarized_content', [])
        if summarized_content_from_state:
            for article in summarized_content_from_state:
                fallback_markdown_content_parts.append(f"### {article.title}\n- Summary: {article.summary}\n[Read More]({article.original_url})\n")
        else:
            fallback_markdown_content_parts.append("No summarized articles were available.\n\n")
        
        fallback_markdown_content_parts.append("## Conclusion\n\nWe anticipate further advancements in this field. Stay updated for more breakthroughs.\n\n**Overall Trends:**\n- No specific new trends identified this week.")
        
        content_markdown = "\n".join(fallback_markdown_content_parts).strip()
        generated_subject = f"{settings.NEWSLETTER_SUBJECT_PREFIX} Generation Failed (Fallback)"

    else: # Normal path: A proper newsletter_outline was generated by Curation Agent
        # --- Invoke LLM for Intro, Conclusion, and Overall Trends TEXT ---
        try:
            logger.info("GENERATION AGENT: Invoking LLM to draft intro, conclusion, and trends text.")
            
            # Create a simplified JSON of the outline to pass to the LLM, focusing on points
            simple_outline_for_llm = {
                "introduction_points": newsletter_outline.introduction_points,
                "conclusion_points": newsletter_outline.conclusion_points,
                "overall_trends": newsletter_outline.overall_trends,
                "sections_summary": [
                    {"name": s.name, "articles_count": len(s.articles)} for s in newsletter_outline.sections
                ]
            }
            newsletter_outline_json_for_llm = json.dumps(simple_outline_for_llm)

            # Define an internal prompt for the LLM that strictly asks for the intro, conclusion, and trends
            internal_llm_prompt = ChatPromptTemplate.from_messages([
                ("system", 
                 "You are an expert content writer for an AI agent development newsletter. "
                 "Based on the provided outline data, draft a compelling introduction, a concise conclusion, "
                 "and a bulleted list of overall trends. "
                 "The introduction should be 3-4 sentences. "
                 "The conclusion should be 2-3 sentences. "
                 "The overall trends should be a bulleted list of 2-3 key trends. "
                 "Output ONLY a JSON object with keys 'introduction', 'conclusion', 'overall_trends'."
                 # ESCAPED CURLY BRACES FOR LITERAL JSON EXAMPLE
                 "Example: {{\"introduction\": \"...\", \"conclusion\": \"...\", \"overall_trends\": [\"- Trend 1\", \"- Trend 2\"]}}" 
                ),
                ("human", 
                 "Here is the newsletter outline data:\n"
                 f"```json\n{{newsletter_outline_json_for_llm}}\n```\n" 
                 "Please generate the introduction, conclusion, and overall trends as described."
                )
            ])
            
            llm_response_for_text = generation_llm.invoke(
                internal_llm_prompt.format_messages(
                    newsletter_outline_json_for_llm=newsletter_outline_json_for_llm
                )
            )
            
            # Safely extract content from LLM response (handle both BaseMessage and str)
            # This uses hasattr to check for .content, otherwise assumes it's a string.
            llm_generated_text_raw = llm_response_for_text.content if hasattr(llm_response_for_text, 'content') else str(llm_response_for_text)
            
            logger.debug(f"Raw LLM response for intro/conclusion/trends: {llm_generated_text_raw[:1000]}...")

            # Use the robust clean_json_string for parsing LLM's response for intro/conclusion/trends
            parsed_intro_conc_trends = {}
            try:
                cleaned_intro_conc_trends_json_str = clean_json_string(llm_generated_text_raw)
                parsed_intro_conc_trends = json.loads(cleaned_intro_conc_trends_json_str)
            except json.JSONDecodeError as e:
                logger.error(f"GENERATION AGENT: Failed to parse LLM's intro/conclusion/trends JSON: {e}. Raw: {llm_generated_text_raw[:500]}...")
                # Fallback to simple strings if parsing fails
                parsed_intro_conc_trends = {
                    "introduction": "This week's digest highlights important developments in AI agent technology.",
                    "conclusion": "We anticipate further advancements in this field. Stay updated for more breakthroughs.",
                    "overall_trends": ["- No specific new trends identified this week."]
                }
            except Exception as e:
                logger.error(f"GENERATION AGENT: Unexpected error during parsing LLM's intro/conclusion/trends: {e}", exc_info=True)
                parsed_intro_conc_trends = {
                    "introduction": "This week's digest highlights important developments in AI agent technology.",
                    "conclusion": "We anticipate further advancements in this field. Stay updated for more breakthroughs.",
                    "overall_trends": ["- No specific new trends identified this week."]
                }

            # Extract the content, ensuring it's a string for paragraphs or a list of strings for trends
            parsed_intro_content = parsed_intro_conc_trends.get('introduction', "This week's digest highlights important developments in AI agent technology.")
            parsed_conclusion_content = parsed_intro_conc_trends.get('conclusion', "We anticipate further advancements in this field. Stay updated for more breakthroughs.")
            parsed_overall_trends = parsed_intro_conc_trends.get('overall_trends', ["- No specific new trends identified this week."])
            
            # Ensure trends are a list, even if LLM gives a single string
            if isinstance(parsed_overall_trends, str):
                # Attempt to convert comma-separated string to list, or just wrap it
                parsed_overall_trends = [f"- {t.strip()}" for t in parsed_overall_trends.split(',') if t.strip()]
                if not parsed_overall_trends: # If splitting empty string, ensure it's not empty list
                    parsed_overall_trends = ["- No specific new trends identified this week."]


        except Exception as e:
            logger.error(f"GENERATION AGENT: Error during LLM invocation for intro/conclusion/trends: {e}", exc_info=True)
            # On LLM invocation failure, use simplified defaults directly
            parsed_intro_content = "This week's digest highlights advancements in AI agent development."
            parsed_conclusion_content = "Stay updated on the latest in AI Agent Development!"
            parsed_overall_trends = ["- No specific new trends identified this week."]
        
        # --- ASSEMBLE FINAL MARKDOWN STRING PROGRAMMATICALLY ---
        final_markdown_parts = []

        # 1. Introduction Heading and Content (from LLM)
        final_markdown_parts.append("## Introduction")
        final_markdown_parts.append(parsed_intro_content)
        final_markdown_parts.append("") # Blank line
        
        # 2. Sections (Built directly from NewsletterOutline)
        for section in newsletter_outline.sections:
            if section.articles: # Only add section if it has articles
                final_markdown_parts.append(f"## {section.name}") # Section Heading
                for article in section.articles:
                    # Clean article title aggressively BEFORE using it
                    clean_article_title = article.title.strip().strip(',').strip('\'').strip('"') # Remove trailing commas/quotes
                    # Remove any "Read More" that might have been part of the title
                    clean_article_title = re.sub(r'\s*\[?Read More\]?\(#?\)\s*$', '', clean_article_title, flags=re.IGNORECASE).strip() 
                    
                    final_markdown_parts.append(f"### {clean_article_title}") # Article title
                    final_markdown_parts.append(f"- Summary: {article.summary.strip()}") # Summary with prefix
                    final_markdown_parts.append(f"[Read More]({article.url.strip()})") # clickable Read More
                    final_markdown_parts.append("") # Blank line after each article
                final_markdown_parts.append("") # Blank line between sections

        # 3. Conclusion (from LLM)
        final_markdown_parts.append("## Conclusion")
        final_markdown_parts.append(parsed_conclusion_content)
        final_markdown_parts.append("")

        # 4. Overall Trends (from LLM)
        final_markdown_parts.append("**Overall Trends:**")
        # Ensure trends are correctly formatted as markdown list items if not already
        if isinstance(parsed_overall_trends, list):
            final_markdown_parts.extend(parsed_overall_trends)
        else: # Fallback if it's somehow a single string not properly parsed to list
            final_markdown_parts.append(f"- {parsed_overall_trends.strip()}")

        final_markdown_parts.append("") # Blank line
        
        content_markdown = "\n".join(final_markdown_parts).strip()


    # --- Final Markdown Cleaning (for any remaining LLM residue or excess newlines) ---
    content_markdown = re.sub(r'^(Here is the generated weekly AI Agent Development Newsletter content:[\n\s]*)*', '', content_markdown, flags=re.IGNORECASE | re.DOTALL).strip()
    content_markdown = re.sub(r'```(?:markdown)?[\s\S]*?```[\s\S]*$', '', content_markdown, flags=re.DOTALL).strip() # Remove any trailing ``` LLM might output
    content_markdown = re.sub(r'\n{3,}', '\n\n', content_markdown).strip() # Reduce excessive blank lines
    
    # Append the system-controlled footer exactly once, and ensure no markdown conversion issues
    # IMPORTANT: The HTML template already has a footer div. We should not have the markdown footer
    # from the content_markdown, and ensure the HTML template is the ONLY source of the footer.
    # The `---` line before the footer is also not desired.
    content_markdown = re.sub(r'\n+---\s*This newsletter is generated by an AI Agent.*$', '', content_markdown, flags=re.DOTALL).strip() # Remove the markdown HR and footer

    # --- Convert Markdown to HTML body ---
    html_content_body = markdown.markdown(content_markdown)

    full_html_with_template = NEWSLETTER_HTML_TEMPLATE.format(
        subject=generated_subject,
        current_year=current_year,
        current_date_header=current_date_formatted_for_header,
        content_html_body=html_content_body # Pass the HTML string converted from markdown
    )

    newsletter_draft = Newsletter(
        date=datetime.now(),
        subject=generated_subject,
        content_markdown=content_markdown,
        content_html=full_html_with_template,
        is_approved=False, # Editorial agent will set this
        revision_attempts=state.get('revision_attempts', 0)
    )
    logger.info("---GENERATION AGENT: Successfully generated newsletter draft.---")

    new_state = state.copy()
    new_state['newsletter_draft'] = newsletter_draft
    return new_state


# Example usage (for testing purposes) - This block is where DATA_DIR and other utils are needed
if __name__ == "__main__":
    print("--- Testing Generation Agent Node (Standalone) ---")
    
    # Try loading newsletter_outline from file
    loaded_outline_data = load_state_from_json("newsletter_outline_state.json", DATA_DIR).get('newsletter_outline', None)
    
    loaded_newsletter_outline = None
    if loaded_outline_data:
        # Manually reconstruct the nested Pydantic models from loaded dictionaries
        sections = []
        for sec_data in loaded_outline_data.get('sections', []):
            articles = [NewsletterArticle(**art_data) for art_data in sec_data.get('articles', [])]
            sections.append(NewsletterSection(name=sec_data.get('name'), articles=articles))
        
        loaded_newsletter_outline = NewsletterOutline(
            date=datetime.fromisoformat(loaded_outline_data.get('date')), # Convert back from ISO format
            introduction_points=loaded_outline_data.get('introduction_points', []),
            sections=sections,
            conclusion_points=loaded_outline_data.get('conclusion_points', []),
            overall_trends=loaded_outline_data.get('overall_trends', [])
        )
        print("Loaded newsletter outline from file.")
    else:
        print("\nWARNING: No newsletter_outline_state.json found or it's empty. Using dummy outline for testing.")
        # This dummy outline simulates a perfect outline from Curation.
        dummy_newsletter_outline = NewsletterOutline(
            date=datetime.now(),
            introduction_points=[
                "This week's digest highlights innovative AI agent developments, framework advancements, and insightful research.",
                "Discover how LangChain and LangGraph are revolutionizing AI workload building and scaling.",
                "Explore the intersection of AI agents, workflows, and LLMs in this week's top stories.",
                "We delve into ethical considerations and practical applications shaping the future of AI."
            ],
            sections=[
                NewsletterSection(
                    name="New Frameworks & Tools",
                    articles=[
                        NewsletterArticle(
                            title="LangChain: Build context-aware reasoning applications",
                            summary="LangChain is a framework for building LLM-powered applications, enabling context-aware reasoning and simplifying development with interoperable components and integrations.",
                            url="[https://github.com/langchain-ai/langchain](https://github.com/langchain-ai/langchain)", # Fixed to be a plain URL, not markdown link
                            category="New Frameworks & Tools"
                        ),
                        NewsletterArticle(
                            title="LangGraph - Build resilient language agents as graphs",
                            summary="LangGraph is a low-level framework for building stateful language agents as graphs, enabling resilient and long-running agent development.",
                            url="[https://github.com/langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)",
                            category="New Frameworks & Tools"
                        ),
                        NewsletterArticle(
                            title="CrewAI: Framework for autonomous agent workflows",
                            summary="CrewAI enables building and deploying automated workflows using any Large Language Model (LLM) and cloud platform, streamlining processes across industries with powerful AI agents.",
                            url="[https://www.crewai.com/](https://www.crewai.com/)",
                            category="New Frameworks & Tools"
                        )
                    ]
                ),
                NewsletterSection(
                    name="Research & Academic Highlights",
                    articles=[
                        NewsletterArticle(
                            title="Multi-agent system - Wikipedia",
                            summary="A multi-agent system (MAS) is a computerized system composed of multiple interacting intelligent agents, enabling cooperative behavior and self-organization.",
                            url="[https://en.wikipedia.org/wiki/Multi-agent_system](https://en.wikipedia.org/wiki/Multi-agent_system)",
                            category="Research & Academic Highlights"
                        ),
                        NewsletterArticle(
                            title="What is a Multi-Agent System? | IBM",
                            summary="A multi-agent system (MAS) consists of multiple artificial intelligence (AI) agents working collectively to perform tasks on behalf of a user or another system, highlighting collective intelligence in AI agent development.",
                            url="[https://www.ibm.com/think/topics/multiagent-system](https://www.ibm.com/think/topics/multiagent-system)",
                            category="Research & Academic Highlights"
                        )
                    ]
                ),
                NewsletterSection(
                    name="Top Insights & Breakthroughs",
                    articles=[
                        NewsletterArticle(
                            title="Major Quantum Computing Advance Made Obsolete by Teenager (2018)",
                            summary="A teenager develops a classical algorithm that outperforms quantum computing's recommendation algorithm, sparking insights for AI agent development.",
                            url="[https://www.quantamagazine.org/teenager-finds-classical-alternative-to-quantum-recommendation-algorithm-20180731/](https://www.quantamagazine.org/teenager-finds-classical-alternative-to-quantum-recommendation-algorithm-20180731/)",
                            category="Top Insights & Breakthroughs"
                        ),
                        NewsletterArticle(
                            title="Building Effective AI Agents - Anthropic",
                            summary="Design AI agents with simplicity, transparency, and careful planning to ensure effectiveness. Prioritize explicit planning steps.",
                            url="[https://www.anthropic.com/research/building-effective-agents](https://www.anthropic.com/research/building-effective-agents)",
                            category="Top Insights & Breakthroughs"
                        ),
                        NewsletterArticle(
                            title="Autonomous agent - Wikipedia",
                            summary="Autonomous agents are AI systems that can perform complex tasks independently, emphasizing self-autonomy and decision-making capabilities.",
                            url="[https://en.wikipedia.org/wiki/Autonomous_agent](https://en.wikipedia.org/wiki/Autonomous_agent)",
                            category="Research & Academic Highlights"
                        )
                    ]
                ),
                NewsletterSection(
                    name="Tutorials & Learning Resources",
                    articles=[
                        NewsletterArticle(
                            title="AI Agent Developer Specialization - Coursera",
                            summary="Develop AI agents using Python, OpenAI tools, and prompt engineering techniques in this Coursera Specialization.",
                            url="[https://www.coursera.org/specializations/ai-agents](https://www.coursera.org/specializations/ai-agents)",
                            category="Tutorials & Learning Resources"
                        )
                    ]
                ),
                NewsletterSection(
                    name="Agentic Workflow Spotlights",
                    articles=[
                        NewsletterArticle(
                            title="What Are Agentic Workflows? Patterns, Use Cases, Examples, and ...",
                            summary="Agentic workflows are series of connected steps taken by an AI agent to achieve a goal, including plan creation with LLMs.",
                            url="[https://weaviate.io/blog/what-are-agentic-workflows](https://weaviate.io/blog/what-are-agentic-workflows)",
                            category="Agentic Workflow Spotlights"
                        ),
                        NewsletterArticle(
                            title="What are Agentic Workflows? | IBM",
                            summary="Agentic workflows: AI-driven processes where autonomous AI agents make decisions, take actions and coordinate tasks with minimal human intervention.",
                            url="[https://www.ibm.com/think/topics/multiagent-system](https://www.ibm.com/think/topics/multiagent-system)",
                            category="Agentic Workflow Spotlights"
                        )
                    ]
                ),
                NewsletterSection(
                    name="Miscellaneous", 
                    articles=[
                        NewsletterArticle(
                            title="No One Knows Anything About AI",
                            summary="A humorous critique of AI's lack of understanding, highlighting the complexity and uncertainty surrounding AI development.",
                            url="[https://calnewport.com/no-one-knows-anything-about-ai/](https://calnewport.com/no-one-knows-anything-about-ai/)", 
                            category="Miscellaneous"
                        )
                    ]
                ),
            ],
            conclusion_points=[
                "The rapid evolution of AI agents continues to redefine what's possible, pushing boundaries in automation and intelligence.",
                "Expect to see increasing integration of agentic workflows across various industries, enhancing efficiency and decision-making.",
                "Continued research into ethical implications and robust agent design remains crucial for sustainable AI development.",
                "Stay informed and engaged as this exciting field of AI agent development continues to unfold."
            ],
            overall_trends=[
                "Increasing focus on modular and adaptable AI agent frameworks.",
                "Growing sophistication in multi-agent coordination and communication.",
                "Expansion of agentic workflows into diverse industry applications."
            ]
        )
        articles_to_generate = dummy_newsletter_outline


    initial_state: AgentState = {
        "raw_articles": [],
        "summarized_content": [], 
        "newsletter_outline": loaded_newsletter_outline, # Use loaded or dummy outline
        "newsletter_draft": None,
        "revision_needed": False,
        "revision_attempts": 0,
        "newsletter_sent": False,
        "delivery_report": None,
        "recipients": [],
    }

    updated_state = generation_agent_node(initial_state)

    print(f"\n--- Generated Newsletter Draft ---")
    if updated_state['newsletter_draft']:
        draft = updated_state['newsletter_draft']
        print(f"Subject: {draft.subject}")
        print(f"\nContent (Markdown):\n{draft.content_markdown}")
        print(f"\nContent (HTML Body - first 1000 chars):\n{draft.content_html[:1000]}...")
        print(f"\nIs Approved: {draft.is_approved}")
        print(f"Revision Attempts: {draft.revision_attempts}")
        
        # --- Save newsletter_draft for next stage testing ---
        save_state_to_json({"newsletter_draft": updated_state['newsletter_draft']}, "newsletter_draft_state.json", DATA_DIR)
        print(f"\nSaved newsletter_draft to {DATA_DIR / 'newsletter_draft_state.json'}")

    else:
        print("No newsletter draft generated. Check logs for errors.")