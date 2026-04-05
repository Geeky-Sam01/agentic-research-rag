import logging
from typing import AsyncGenerator, Optional, List

from pydantic import BaseModel, Field
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.llm_clients import get_llm_with_fallbacks
from app.services.prompts import RAG_STREAM_PROMPT, RAG_STRUCTURED_PROMPT
from app.services.response_parser import parse_rag_response, SummaryCard

logger = logging.getLogger(__name__)


from typing import Literal

# ── 1. Define the Schema the LLM must follow ──────────────────────────────
class MetricItem(BaseModel):
    label: str = Field(description="Name of the metric")
    value: str = Field(description="Numeric or categorical value of the metric")
    unit: Optional[str] = Field(default=None, description="Optional unit (e.g., %, USD)")

class MetricBlock(BaseModel):
    type: Literal["metric"]
    title: str = Field(description="Title of the metric group")
    data: List[MetricItem] = Field(description="List of metric data points")

class TableBlock(BaseModel):
    type: Literal["table"]
    title: str = Field(description="Title of the table")
    columns: List[str] = Field(description="List of column headers")
    rows: List[List[str]] = Field(description="Table rows")

class SummaryBlock(BaseModel):
    type: Literal["summary"]
    title: str = Field(description="Title of the summary")
    text: str = Field(description="Text content of the summary")

Block = MetricBlock | TableBlock | SummaryBlock

class FinSightResponse(BaseModel):
    query: str = Field(description="The user's original query")
    intent: str = Field(description="Underlying intent of the query")
    confidence: float = Field(description="Confidence score between 0 and 1")
    blocks: List[Block] = Field(description="Extracted financial insight blocks")

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
    
    # ⚡ THE MAGIC LINE: Bind the Pydantic schema with strict mode
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
        return SummaryCard(
            headline="Error rendering response", 
            key_points=[f"We encountered an error with structured outputs: {str(e)}"], 
            conclusion="Please try again or use standard stream mode."
        ).model_dump()