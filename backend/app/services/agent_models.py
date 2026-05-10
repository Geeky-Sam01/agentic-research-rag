from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Intent(str, Enum):
    DATA = "DATA"
    PERFORMANCE = "PERFORMANCE"
    DISCOVERY = "DISCOVERY"
    DOCUMENT = "DOCUMENT"
    CALCULATOR = "CALCULATOR"
    GENERAL = "GENERAL"

class Operation(BaseModel):
    type: str
    confidence: float = 1.0
    evidence: List[str] = Field(default_factory=list)

class SubTask(BaseModel):
    """A single decomposed sub-task from the query rewriter."""
    id: str = Field(description="Unique task identifier, e.g. 'task_1'")
    intent: str  # Use str instead of Enum to avoid LangGraph deserialization warnings
    query: str = Field(description="Specific, actionable query for the agent")
    priority: int = Field(ge=1, le=3, description="1 = highest priority")
    requires: List[str] = Field(default_factory=list, description="IDs of tasks this depends on")
    operations: List[Operation] = Field(default_factory=list, description="Extracted operations for this task")

class Entities(BaseModel):
    """Named entities extracted from the user query."""
    fund: Optional[str] = Field(default=None, description="Fund name, e.g. 'SBI Bluechip'")
    amc: Optional[str] = Field(default=None, description="AMC / fund house name")
    scheme_code: Optional[str] = Field(default=None, description="Numeric scheme code if mentioned")
    category: Optional[str] = Field(default=None, description="Fund category e.g. 'large_cap'")

class QueryPlan(BaseModel):
    """Structured output from the query rewriter."""
    tasks: List[SubTask] = Field(default_factory=list, description="Max 3 sub-tasks")
    entities: Entities = Field(default_factory=Entities, description="Extracted named entities")
    complexity: Literal["LOW", "MEDIUM", "HIGH"] = Field(default="LOW", description="Estimated query complexity")
    needs_clarification: bool = Field(default=False)
    clarification_question: Optional[str] = None

class AgentResult(BaseModel):
    """Structured output from each specialist agent execution."""
    task_id: str
    intent: str
    answer: str
    data: dict = Field(default_factory=dict)
    sources: list = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    success: bool = True
    error: Optional[str] = None

class IntentCheckResult(BaseModel):
    intent: Literal["DATA","PERFORMANCE","DISCOVERY","DOCUMENT","CALCULATOR","GENERAL"]
    confidence: float = Field(ge=0.0, le=1.0)
    completeness_score: float = Field(ge=0.0, le=1.0)
    ambiguity_score: float = Field(ge=0.0, le=1.0)
    missing_fields: List[str] = Field(default_factory=list)
    decision: Literal["EXECUTE","FALLBACK","CLARIFY"]

class _IntentClass(BaseModel):
    intent: Literal["DATA", "PERFORMANCE", "DISCOVERY", "DOCUMENT", "CALCULATOR", "GENERAL"]
