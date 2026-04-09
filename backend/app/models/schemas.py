from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# Request/Response Models
class DocumentUploadResponse(BaseModel):
    success: bool
    message: str
    totalIndexed: int
    chunksCreated: int
    embeddingModel: str
    embeddingDimension: int
    suggested_questions: Optional[List[str]] = None

class QueryRequest(BaseModel):
    query: str
    stream: bool = True

class Source(BaseModel):
    text: str
    source: str
    similarity: str

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[Source]
    resultsFound: int
    model: str
    embedding: str

class StatsResponse(BaseModel):
    indexed: int
    sources: List[str]
    stats: dict

# --- FinSight Structured Responses ---
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
