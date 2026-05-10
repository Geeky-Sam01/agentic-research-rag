import logging
import re
from enum import Enum
from typing import Literal, Optional, Tuple
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.services.llm import get_planner_llm
from app.services.prompts import ROUTER_CLASSIFIER_PROMPT, ROUTER_GENERATOR_PROMPT
from app.services.capabilities import (
    detect_requested_capability, 
    SUPPORTED_CAPABILITIES, 
    get_unsupported_message
)

logger = logging.getLogger(__name__)

@dataclass
class RouteContext:
    """Session context passed to the router for better routing decisions."""
    last_fund_name: Optional[str] = None
    last_fund_code: Optional[str] = None
    last_response_mode: Optional[str] = None
    last_intent: Optional[str] = None
    turn_count: int = 0  # how many turns in this session

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


def heuristic_route(message: str, context: RouteContext = None) -> RouteDecision:
    """Fast deterministic routing, now with session awareness."""
    msg_lower = message.lower()

    # ── 1. Follow-up detection using session context ──
    # If we have an active fund in context and the query is a short follow-up, route to TOOL.
    if context and context.last_fund_name:
        # Reference-word detection
        reference_words = {"it", "this", "that", "those", "the fund", "more", "details"}
        if any(word in msg_lower.split() for word in reference_words):
            return RouteDecision.TOOL

        # Comparative/Elaboration follow-ups
        comparison_keys = ["compare", "vs", "versus", "better", "alternative", "than"]
        if any(k in msg_lower for k in comparison_keys):
            return RouteDecision.TOOL

        elaboration_keys = ["tell me more", "explain", "elaborate", "details", "why", "how"]
        if any(k in msg_lower for k in elaboration_keys):
            # But only if it's not a generic concept explanation query
            if not is_simple_explanation_query(message):
                return RouteDecision.TOOL

    # ── 2. SIP routing ──
    if "sip" in msg_lower:
        if is_sip_calculation_query(message):
            return RouteDecision.TOOL
        elif is_simple_explanation_query(message):
            return RouteDecision.NO_TOOL
            
    # ── 3. Explanation queries ──
    if is_simple_explanation_query(message):
        return RouteDecision.NO_TOOL

    # ── 3.5 Capability Gate (New) ──
    # Intercept unsupported requests before they hit the expensive graph
    capability = detect_requested_capability(message)
    if capability:
        supported = SUPPORTED_CAPABILITIES.get(capability, False)
        logger.info(
            f"CapabilityCheck: query='{message[:40]}...', capability='{capability}', supported={supported}"
        )
        if not supported:
            return RouteDecision.NO_TOOL

    # ── 4. Finance keywords ──
    if any(term in msg_lower for term in FINANCE_TERMS):
        return RouteDecision.TOOL

    # ── 5. Explicit history signals ──
    history_signals = {"last", "previous", "mentioned", "earlier", "talked about", "before"}
    if any(sig in msg_lower for sig in history_signals):
        return RouteDecision.TOOL

    return RouteDecision.AMBIGUOUS


# ── LAYER 2: LIGHTWEIGHT CLASSIFIER ────────────────────────────────────────────

class _RouteClass(BaseModel):
    route: Literal["no_tool", "tool"] = Field(description="The chosen route")
    capability: Optional[str] = Field(description="The detected canonical capability (nav, aum, sip_calculation, etc.)")


async def lightweight_classifier(message: str, context: RouteContext = None) -> Tuple[RouteDecision, Optional[str]]:
    """Only used if heuristic routing is ambiguous. Now context-aware and capability-aware."""
    try:
        # Build session hint for the LLM
        hint_parts = []
        if context and context.last_fund_name:
            hint_parts.append(f"Context: Last discussed fund was '{context.last_fund_name}'.")
        if context and context.turn_count > 1:
            hint_parts.append("This is a follow-up in an ongoing conversation.")

        session_hint = " ".join(hint_parts) if hint_parts else "No prior context."

        classifier = get_planner_llm().with_structured_output(_RouteClass, method="function_calling")
        res = await classifier.ainvoke(
            [
                SystemMessage(content=ROUTER_CLASSIFIER_PROMPT),
                SystemMessage(content=f"[{session_hint}]"),
                HumanMessage(content=message),
            ]
        )
        decision = RouteDecision.TOOL if res.route == "tool" else RouteDecision.NO_TOOL
        return decision, res.capability
    except Exception as e:
        logger.error(f"Lightweight classifier failed: {e}")
        return RouteDecision.TOOL, None  # Fallback to safer route


async def stream_no_tool_response(message: str, context: RouteContext = None):
    """Stream a response for NO_TOOL routes using the planner LLM."""
    try:
        llm = get_planner_llm()
        messages = [SystemMessage(content=ROUTER_GENERATOR_PROMPT)]
        
        # Add context if available
        if context and context.last_fund_name:
            messages.append(SystemMessage(content=f"[Context: The last mutual fund discussed was '{context.last_fund_name}']."))
            
        messages.append(HumanMessage(content=message))
        
        response = await llm.ainvoke(messages)
        words = response.content.split(" ")
        for i, word in enumerate(words):
            yield word if i == 0 else " " + word
    except Exception as e:
        logger.error(f"Failed to stream NO_TOOL response: {e}")
        yield "I'm having trouble processing that right now. Could you please ask about specific mutual funds?"


async def generate_no_tool_response(message: str, context: RouteContext = None) -> str:
    """Generate a quick response for NO_TOOL routes using the planner LLM."""
    try:
        llm = get_planner_llm()
        messages = [SystemMessage(content=ROUTER_GENERATOR_PROMPT)]
        
        if context and context.last_fund_name:
            messages.append(SystemMessage(content=f"[Context: The last mutual fund discussed was '{context.last_fund_name}']."))
            
        messages.append(HumanMessage(content=message))
        
        res = await llm.ainvoke(messages)
        return res.content
    except Exception as e:
        logger.error(f"Failed to generate NO_TOOL response: {e}")
        return "I'm having trouble processing that right now. Could you please ask about specific mutual funds?"


# ── TOP-LEVEL ROUTER FUNCTION ──────────────────────────────────────────────────

async def route_message(message: str, context: RouteContext = None) -> Tuple[str, str]:
    """
    Returns:
    ("static", response)
    ("no_tool", response)
    ("tool", "")
    """
    # 1. Static Gate (Regex - Fast & Cheap)
    static_res = static_gate(message)
    if static_res is not None:
        return ("static", static_res)

    # 2. Heuristic Check (Strict Keyword match - Fast)
    # Note: We keep simple FINANCE_TERMS here but leave ambiguity to the Smart Router
    route = heuristic_route(message, context)
    
    # 3. Smart Router (LLM - Accurate & Context-Aware)
    # If heuristic is ambiguous, or if it matched TOOL, we verify the capability.
    capability = None
    if route == RouteDecision.AMBIGUOUS:
        route, capability = await lightweight_classifier(message, context)
    else:
        # For non-ambiguous TOOL routes, quickly check capability to handle unsupported ones
        capability = detect_requested_capability(message)

    # 4. Capability Gate (Enforce Registry)
    if capability:
        supported = SUPPORTED_CAPABILITIES.get(capability, False)
        if not supported:
            # If it's an explanation query, allow it to proceed to NO_TOOL
            if not is_simple_explanation_query(message) or _has_fund_entity(message):
                logger.info(f"CapabilityGate: blocking unsupported '{capability}'")
                return ("no_tool", get_unsupported_message(capability))

    # 5. Generate response for NO_TOOL
    if route == RouteDecision.NO_TOOL:
        res = await generate_no_tool_response(message, context)
        return ("no_tool", res)

    return ("tool", "")
