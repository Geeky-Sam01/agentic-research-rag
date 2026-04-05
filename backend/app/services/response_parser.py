from typing import List, Literal, Union, Dict, Any
from pydantic import BaseModel, Field

class TableResponse(BaseModel):
    type: Literal["table"] = "table"
    title: str = Field(description="A descriptive title for the table.")
    headers: List[str] = Field(description="List of column headers.")
    rows: List[List[str]] = Field(description="List of rows, where each row is a list of strings corresponding to the headers.")

class CardItem(BaseModel):
    heading: str
    body: str
    tag: str

class CardsResponse(BaseModel):
    type: Literal["cards"] = "cards"
    title: str = Field(description="A descriptive title for the card collection.")
    cards: List[CardItem]

class SummaryCard(BaseModel):
    type: Literal["summary"] = "summary"
    headline: str
    key_points: List[str]
    conclusion: str

class MixedBlock(BaseModel):
    block_type: str = Field(description="Type of the block: 'summary', 'table', or 'cards'.")
    content: Any = Field(description="The actual content object matching the block_type schemas.")

class MixedResponse(BaseModel):
    type: Literal["mixed"] = "mixed"
    blocks: List[MixedBlock]

StructuredResponse = Union[TableResponse, CardsResponse, SummaryCard, MixedResponse]

def parse_rag_response(data: dict) -> StructuredResponse:
    """Parses raw dictionary data into the corresponding structured format."""
    type_val = data.get("type", "summary")
    try:
        if type_val == "table":
            return TableResponse(**data)
        elif type_val == "cards":
            return CardsResponse(**data)
        elif type_val == "mixed":
            return MixedResponse(**data)
        else:
            return SummaryCard(**data)
    except BaseException:
        # Fallback to generic summary block on parse failure
        return SummaryCard(
            type="summary",
            headline="Summary Response",
            key_points=[str(data)],
            conclusion="Response could not be properly structured."
        )
