import logging
from typing import Any, AsyncGenerator, List, Optional

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.core.config import settings
from app.services.agent_tools import ALL_MF_TOOLS
from app.services.prompts import MF_RESEARCH_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def create_research_agent(model_name: Optional[str] = None):
    """
    Creates a LangGraph-based ReAct agent for mutual fund research.
    """
    model = model_name or settings.LLM_MODEL
    logger.info(f"Creating research agent with model: {model}")
    
    # Initialize the LLM (OpenRouter compatible via ChatOpenAI)
    # Using temperature 0 for precision in financial data
    llm = ChatOpenAI(
        model=model, 
        temperature=0,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        streaming=True
    )

    # Agent initialization
    return create_react_agent(llm, ALL_MF_TOOLS,prompt=MF_RESEARCH_SYSTEM_PROMPT)

async def run_agent_query(user_input: str, chat_history: List[Any] = None) -> dict:
    """
    Standard async runner for the research agent (non-streaming).
    Returns a dict with 'output' (text) and 'sources' (list).
    """
    logger.info(f"Running agent query: '{user_input[:50]}...'")
    agent = create_research_agent()
    
    try:
        # Use a dictionary to store tool outputs for the unified response
        sources = []
        
        # In non-streaming mode, we can use astream to capture events 
        # or use run_agent_query with result parsing.
        # But to capture tool outputs simply, we'll use astream_events even here.
        final_output = ""
        async for event in agent.astream_events(
            {"messages": [("user", user_input)]},
            version="v2"
        ):
            kind = event["event"]
            if kind == "on_chat_model_end":
                # Final content is in the last model message
                if "output" in event["data"]:
                     final_output = event["data"]["output"].content
            elif kind == "on_tool_end":
                if event["name"] == "read_factsheet":
                    output = event["data"]["output"]
                    if isinstance(output, dict) and "sources" in output:
                        sources = output["sources"]

        logger.info(f"Agent execution complete. Sources found: {len(sources)}")
        return {
            "output": final_output,
            "sources": sources
        }
        
    except Exception as e:
        logger.error(f"Agent execution error: {str(e)}", exc_info=True)
        return {
            "output": f"I encountered an error while researching: {str(e)}",
            "sources": []
        }

async def stream_agent_query(user_input: str, chat_history: List[Any] = None) -> AsyncGenerator[dict, None]:
    """
    Granular streaming runner for the research agent.
    Yields LangChain stream events (astream_events v2).
    """
    logger.info(f"Streaming agent query: '{user_input[:50]}...'")
    agent = create_research_agent()
    
    try:
        async for event in agent.astream_events(
            {"messages": [("user", user_input)]},
            version="v2"
        ):
            yield event
            
    except Exception as e:
        logger.error(f"Agent streaming error: {str(e)}", exc_info=True)
        # We don't yield the error as a dict here, we let the API handler catch it
        raise e
