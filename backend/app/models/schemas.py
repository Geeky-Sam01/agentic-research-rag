from pydantic import BaseModel
from typing import List, Optional

# Request/Response Models
class DocumentUploadResponse(BaseModel):
    success: bool
    message: str
    totalIndexed: int
    chunksCreated: int
    embeddingModel: str
    embeddingDimension: int

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
