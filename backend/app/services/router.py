import logging
import re
from enum import Enum
from typing import Literal, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.services.llm import get_planner_llm
from app.services.prompts import ROUTER_CLASSIFIER_PROMPT, ROUTER_GENERATOR_PROMPT

logger = logging.getLogger(__name__)

# ── LAYER 0: STATIC GATE ───────────────────────────────────────────────────────

_GREETING_RE = re.compile(
    r"^(?:hi+|hey+|hello+|yo|sup|greetings|good\s*(?:morning|afternoon|evening|night)|thanks+|thank\s*you|bye+)$",
    re.IGNORECASE,
)

_FAQ_PATTERNS = {
    re.compile(r"what\s+can\s+you\s+do", re.I):
        "I can help with mutual fund analysis, NAV lookup, SIP calculations, fund comparisons, and factsheet analysis.",

    re.compile(r"who\s+are\s+you", re.I):
        "I'm FinSight, a mutual fund research assistant.",

    re.compile(r"how\s+does\s+this\s+work", re.I):
        "You can ask me about mutual funds, NAV, SIP calculations, returns, holdings, and comparisons.",
}

def static_gate(message: str) -> Optional[str]:
    """
    Returns a direct response if handled.
    Returns None if the query should continue routing.
    """
    clean_msg = message.strip()
    if not clean_msg:
        return "Please ask a question."
    
    if _GREETING_RE.match(clean_msg):
        return "Hello! I'm FinSight. How can I help you with your mutual fund research today?"
        
    for pattern, response in _FAQ_PATTERNS.items():
        if pattern.search(clean_msg):
            return response
            
    return None


# ── LAYER 1: HEURISTIC ROUTER ──────────────────────────────────────────────────

FINANCE_TERMS = {
    "nav", "sip", "mutual fund", "returns", "expense ratio", "aum",
    "holdings", "large cap", "mid cap", "small cap", "elss", "fund",
    "portfolio", "xirr",
}

class RouteDecision(str, Enum):
    NO_TOOL = "no_tool"
    TOOL = "tool"
    AMBIGUOUS = "ambiguous"


def is_sip_calculation_query(message: str) -> bool:
    """
    Return True only if:
    - SIP intent exists
    - amount exists
    - duration exists
    """
    msg_lower = message.lower()
    has_sip = "sip" in msg_lower or "systematic investment" in msg_lower
    has_amount = "₹" in message or bool(re.search(r"\b\d+(?:,\d+)*(?:k|l|m)?\b", msg_lower))
    has_duration = bool(re.search(r"\b\d+\s*(?:year|yr|month|mo)s?\b", msg_lower))
    return has_sip and has_amount and has_duration

def is_simple_explanation_query(message: str) -> bool:
    """Detect queries asking about concepts, not specific funds."""
    msg_lower = message.lower()
    
    # Must start with an explanation pattern
    if not re.match(r"^(what is|what are|explain|define|how does .* work|tell me about)\b", msg_lower):
        return False
    
    # If it mentions a specific fund entity -> route to TOOL
    if _has_fund_entity(message) or _has_scheme_code(message):
        return False
    
    # If it mentions fund data concepts -> route to TOOL
    fund_data_signals = ["nav", "returns", "holdings", "expense ratio", "aum", 
                         "exit load", "portfolio", "factsheet", "scheme code"]
    if any(signal in msg_lower for signal in fund_data_signals):
        return False
    
    # Pure concept explanations -> NO_TOOL
    return True


def _has_fund_entity(message: str) -> bool:
    """Check if the message references a specific fund house or fund name."""
    msg_lower = message.lower()
    known_amcs = ["sbi", "hdfc", "icici", "axis", "parag", "ppfas", "nippon", 
                  "quant", "kotak", "mirae", "tata", "uti", "idfc",
                  "canara robeco", "dsp", "franklin", "fidelity", "bajaj",
                  "bandhan", "itm", "quantum", "sundaram", "edelweiss"]
    if any(amc in msg_lower for amc in known_amcs):
        return True
    return False


def _has_scheme_code(message: str) -> bool:
    """Check if the message contains a 5-6 digit scheme code."""
    return bool(re.search(r"\b\d{5,6}\b", message))


def heuristic_route(message: str) -> RouteDecision:
    """Fast deterministic routing."""
    msg_lower = message.lower()
    
    # Check SIP specifically: explanation vs calculation
    if "sip" in msg_lower:
        if is_sip_calculation_query(message):
            return RouteDecision.TOOL
        elif is_simple_explanation_query(message):
            return RouteDecision.NO_TOOL
            
    # Check simple explanations for other finance terms
    if is_simple_explanation_query(message):
        return RouteDecision.NO_TOOL

    # If finance keywords exist: return TOOL
    if any(term in msg_lower for term in FINANCE_TERMS):
        return RouteDecision.TOOL

    # If it lacks finance keywords, it might be casual/chitchat or ambiguous
    return RouteDecision.AMBIGUOUS


# ── LAYER 2: LIGHTWEIGHT CLASSIFIER ────────────────────────────────────────────

class _RouteClass(BaseModel):
    route: Literal["no_tool", "tool"] = Field(description="The chosen route")


async def lightweight_classifier(message: str) -> RouteDecision:
    """Only used if heuristic routing is ambiguous."""
    try:
        classifier = get_planner_llm().with_structured_output(_RouteClass, method="function_calling")
        res = await classifier.ainvoke(
            [
                SystemMessage(content=ROUTER_CLASSIFIER_PROMPT),
                HumanMessage(content=message),
            ]
        )
        return RouteDecision.TOOL if res.route == "tool" else RouteDecision.NO_TOOL
    except Exception as e:
        logger.error(f"Lightweight classifier failed: {e}")
        return RouteDecision.TOOL  # Fallback to safer route


async def stream_no_tool_response(message: str):
    """Stream a response for NO_TOOL routes using the planner LLM."""
    try:
        llm = get_planner_llm()
        # Non-streaming invocation, then yield word-by-word for progressive rendering
        response = await llm.ainvoke(
            [
                SystemMessage(content=ROUTER_GENERATOR_PROMPT),
                HumanMessage(content=message),
            ]
        )
        words = response.content.split(" ")
        for i, word in enumerate(words):
            yield word if i == 0 else " " + word
    except Exception as e:
        logger.error(f"Failed to stream NO_TOOL response: {e}")
        yield "I'm having trouble processing that right now. Could you please ask about specific mutual funds?"


async def generate_no_tool_response(message: str) -> str:
    """Generate a quick response for NO_TOOL routes using the planner LLM."""
    try:
        llm = get_planner_llm()
        res = await llm.ainvoke(
            [
                SystemMessage(content=ROUTER_GENERATOR_PROMPT),
                HumanMessage(content=message),
            ]
        )
        return res.content
    except Exception as e:
        logger.error(f"Failed to generate NO_TOOL response: {e}")
        return "I'm having trouble processing that right now. Could you please ask about specific mutual funds?"


# ── TOP-LEVEL ROUTER FUNCTION ──────────────────────────────────────────────────

async def route_message(message: str) -> Tuple[str, str]:
    """
    Returns:
    ("static", response)
    ("no_tool", response)
    ("tool", "")
    """
    # 1. Static Gate
    static_res = static_gate(message)
    if static_res is not None:
        return ("static", static_res)

    # 2. Heuristic Router
    route = heuristic_route(message)
    
    # 3. Lightweight Classifier (if ambiguous)
    if route == RouteDecision.AMBIGUOUS:
        route = await lightweight_classifier(message)

    # 4. Generate response for NO_TOOL
    if route == RouteDecision.NO_TOOL:
        res = await generate_no_tool_response(message)
        return ("no_tool", res)

    return ("tool", "")
