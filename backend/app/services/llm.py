import logging
from typing import AsyncGenerator, Optional, List


from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.llm_clients import get_llm_with_fallbacks
from app.services.prompts import RAG_STREAM_PROMPT, RAG_STRUCTURED_PROMPT

logger = logging.getLogger(__name__)


from app.models.schemas import FinSightResponse

# ── 2. Streaming (Unchanged) ──────────────────────────────────────────────
async def generate_answer_stream(
    query: str, 
    context: str, 
    model_override: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Streaming: yields text chunks directly. Used for standard Markdown answers."""
    
    primary = model_override if model_override else settings.LLM_MODEL
    llm = get_llm_with_fallbacks(primary, streaming=True)
    chain = RAG_STREAM_PROMPT | llm
    
    try:
        async for chunk in chain.astream({"query": query, "context": context}):
            text = chunk.content
            if text:
                yield text
    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        yield f"ERROR: {str(e)}"


# ── 3. Structured Output (Upgraded) ───────────────────────────────────────
async def generate_answer_structured(
    query: str, 
    context: str, 
    model_override: Optional[str] = None
) -> dict:
    """Non-streaming: Uses native OpenRouter structured outputs. No more regex/json parsing."""
    
    primary = model_override if model_override else settings.LLM_MODEL
    llm = get_llm_with_fallbacks(primary, streaming=False).bind(temperature=0.1)
    
    structured_llm = llm.with_structured_output(FinSightResponse, strict=True)
    
    chain = RAG_STRUCTURED_PROMPT | structured_llm
    
    try:
        result: FinSightResponse = await chain.ainvoke({"query": query, "context": context})
        
        # Inject an overriding type parameter so the UI renderer knows it's a FinSightResponse
        dump = result.model_dump()
        dump["type"] = "finsight"
        return dump
        
    except Exception as e:
        logger.error(f"LLM Structured Output error: {str(e)}")
        return {
        "type": "finsight",
        "query": query,
        "intent": "error",
        "confidence": 0.0,
        "blocks": [{
            "type": "summary",
            "title": "Error",
            "text": f"Could not generate structured response: {str(e)}. Please try again or switch to Explainer Mode."
        }]
    }