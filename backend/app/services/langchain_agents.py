"""
FinSight — Agentic Research Pipeline (v3)

Graph: START → Rewriter → Controller → Executor(loop) → Synthesizer → END
                ↘ Clarify → END

Features:
  - Structured query decomposition (max 5 sub-tasks)
  - Execution controller with guardrails (max 5 agents, max 1 DOCUMENT)
  - Shared context layer for cross-agent entity resolution
  - Structured agent outputs (AgentResult)
  - Synthesizer for multi-agent output fusion
  - Failure handling per-task (never breaks full response)
"""

import json
import logging
import re
import time
from typing import Annotated, AsyncGenerator, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from psycopg_pool import AsyncConnectionPool
from typing_extensions import TypedDict

from app.services.agent_models import (
    AgentResult,
    Intent,
    IntentCheckResult,
    Operation,
    QueryPlan,
    SubTask,
    _IntentClass,
)
from app.services.agent_tools import (
    CALCULATOR_TOOLS,
    DATA_TOOLS,
    DISCOVERY_TOOLS,
    DOCUMENT_TOOLS,
    PERFORMANCE_TOOLS,
)
from app.services.capabilities import detect_requested_capability
from app.services.fund_resolver import resolve_fund
from app.services.llm import get_llm, get_planner_llm
from app.services.prompts import (
    CALCULATOR_AGENT_PROMPT,
    DATA_AGENT_PROMPT,
    DISCOVERY_AGENT_PROMPT,
    DOCUMENT_AGENT_PROMPT,
    GENERAL_AGENT_PROMPT,
    PERFORMANCE_AGENT_PROMPT,
    QUERY_REWRITER_PROMPT,
    SYNTHESIZER_PROMPT,
)
from app.services.router import RouteContext, route_message, stream_no_tool_response

try:
    from langfuse.callback import CallbackHandler as LangfuseHandler

    _langfuse_available = True
except ImportError:
    _langfuse_available = False



logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 1. SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════════════════════
# 2. STATE
# ══════════════════════════════════════════════════════════════════════════════


def _append_results(existing: list, new: list) -> list:
    """Reducer: accumulate agent results across executor iterations. Pass None to clear."""
    if new is None:
        return []
    return (existing or []) + (new or [])


class PipelineState(TypedDict):
    """Full pipeline state for the agentic graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    intent_check: Optional[dict]  # IntentCheckResult dict
    query_plan: Optional[dict]
    shared_context: Annotated[dict, lambda x, y: {**x, **y}]
    pending_tasks: list[dict]
    current_task_index: int
    agent_results: Annotated[list[dict], _append_results]
    sources: list[dict]
    error: Optional[str]
    last_response_mode: Optional[str]  # "concise" | "analytical" | "detailed"
    requested_capability: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# 3. SINGLETON LLMs
# ══════════════════════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════════════════════
# 4. CACHED AGENTS (config-driven)
# ══════════════════════════════════════════════════════════════════════════════

AGENT_CONFIG = {
    "DATA": {"tools": DATA_TOOLS, "prompt": DATA_AGENT_PROMPT},
    "PERFORMANCE": {"tools": PERFORMANCE_TOOLS, "prompt": PERFORMANCE_AGENT_PROMPT},
    "DISCOVERY": {"tools": DISCOVERY_TOOLS, "prompt": DISCOVERY_AGENT_PROMPT},
    "DOCUMENT": {"tools": DOCUMENT_TOOLS, "prompt": DOCUMENT_AGENT_PROMPT},
    "CALCULATOR": {"tools": CALCULATOR_TOOLS, "prompt": CALCULATOR_AGENT_PROMPT},
    "GENERAL": {"tools": [], "prompt": GENERAL_AGENT_PROMPT},
}

_cached_agents: dict = {}


def _get_agent(intent: str):
    """Get a cached ReAct agent for the given intent."""
    if intent not in _cached_agents:
        cfg = AGENT_CONFIG.get(intent, AGENT_CONFIG["GENERAL"])
        logger.info(f"Creating ReAct agent: {intent}")
        _cached_agents[intent] = create_react_agent(
            get_llm(),
            cfg["tools"],
            prompt=cfg["prompt"],
        )
    return _cached_agents[intent]


# ── Ambiguity detection constants & requirements ────────────────────────────────────────────
INTENT_REQUIREMENTS = {
    "PERFORMANCE": ["category_or_fund"],
    "CALCULATOR": ["amount", "tenure", "return_rate"],
    "DATA": ["fund"],
    "DOCUMENT": ["fund"],
    "DISCOVERY": [],
    "GENERAL": [],
}

FIELD_QUESTIONS = {
    "fund": {
        "q": "Which mutual fund are you referring to?",
        "examples": ["SBI Bluechip Fund", "Parag Parikh Flexi Cap", "Scheme code 119551"],
    },
    "category_or_fund": {
        "q": "Do you have a specific fund in mind or a category?",
        "examples": ["Large-cap funds", "Mid-cap funds", "Any SBI fund"],
    },
    "horizon": {"q": "What is your investment horizon?", "examples": ["1–3 years", "3–5 years", "5+ years"]},
    "risk": {
        "q": "What is your risk preference?",
        "examples": ["Low risk (stable)", "Moderate risk", "High risk (aggressive growth)"],
    },
    "amount": {"q": "What amount do you want to invest?", "examples": ["₹5000 per month", "₹1 lakh lump sum"]},
    "tenure": {"q": "For how long will you invest?", "examples": ["2 years", "5 years", "10 years"]},
    "return_rate": {"q": "What is the expected annual return percentage?", "examples": ["12%", "15% annual return"]},
}

INTENT_PREFIX = {
    "PERFORMANCE": "To recommend suitable funds,",
    "CALCULATOR": "To calculate accurate returns,",
    "DATA": "To fetch correct data,",
    "DOCUMENT": "To analyze the fund,",
}

DEFAULT_CLARIFICATION = (
    "Could you be more specific? I can help with:\n\n"
    '- 📊 **NAV / Fund data**: *"NAV of SBI Bluechip Fund"*\n'
    '- 🏆 **Top funds**: *"Best large-cap funds for 5 years"*\n'
    '- 🔍 **Fund discovery**: *"List all HDFC equity funds"*\n'
    '- 📄 **Holdings/Strategy**: *"Holdings of Parag Parikh Flexi Cap"*\n'
    '- 🧮 **SIP Calculator**: *"₹5000/month for 3 years at 12%"*'
)


CATEGORIES = ["large cap", "mid cap", "small cap", "flexi cap", "debt", "hybrid"]

# ── Operations Metadata (V3 Migration) ────────────────────────────────────────────────────────
SUPPORTED_OPERATIONS = {
    "fund_resolution",
    "nav_lookup",
    "historical_return_lookup",
    "fund_category_lookup",
    "sip_projection",
    "historical_sip_simulation",
    "factsheet_analysis",
    "holdings_analysis",
    "fund_comparison",
    "fund_ranking",
    "qualitative_risk_analysis",
}

OPERATION_TOOL_MAP = {
    "nav_lookup": ["get_scheme_quote"],
    "historical_return_lookup": ["get_historical_nav"],
    "sip_projection": ["calculate_projected_sip_returns"],
    "historical_sip_simulation": ["calculate_historical_sip_returns"],
    "factsheet_analysis": ["read_factsheet"],
    "fund_resolution": ["resolve_fund"],
}

OPERATION_PRIORITY = [
    "fund_resolution",
    "nav_lookup",
    "historical_return_lookup",
    "sip_projection",
    "factsheet_analysis",
    "fund_comparison",
]

def extract_operations(query: str, features: dict) -> list[dict]:
    ops = []
    ql = query.lower()

    def add_op(op_type: str, confidence: float, evidence: list[str]):
        ops.append({
            "type": op_type,
            "confidence": confidence,
            "evidence": evidence,
        })

    # ─────────────────────────────
    # Fund Resolution
    # ─────────────────────────────
    fund_evidence = []

    if features.get("has_fund"):
        fund_evidence.append("has_fund_feature")

    if any(k in ql for k in [
        "sbi", "icici", "hdfc", "axis",
        "ppfas", "parag", "quant",
        "nippon", "motilal", "tata", "dsp"
    ]):
        fund_evidence.append("fund_keyword")

    if fund_evidence:
        add_op(
            "fund_resolution",
            0.95,
            fund_evidence
        )

    # ─────────────────────────────
    # SIP Projection
    # ─────────────────────────────
    sip_evidence = []

    if features.get("has_amount"):
        sip_evidence.append("amount")

    if features.get("has_tenure"):
        sip_evidence.append("tenure")

    if features.get("has_return_rate"):
        sip_evidence.append("return_rate")

    if any(k in ql for k in [
        "sip", "future value", "projection",
        "corpus", "invest", "calculate"
    ]):
        sip_evidence.append("sip_keyword")

    if len(sip_evidence) >= 2:
        add_op(
            "sip_projection",
            min(0.99, 0.5 + len(sip_evidence) * 0.1),
            sip_evidence
        )

    # ─────────────────────────────
    # Comparison
    # ─────────────────────────────
    compare_evidence = []

    if features.get("is_comparative"):
        compare_evidence.append("comparative_feature")

    if any(k in ql for k in [
        "compare", "vs", "better",
        "which is better"
    ]):
        compare_evidence.append("comparison_keyword")

    if compare_evidence:
        add_op(
            "fund_comparison",
            0.9,
            compare_evidence
        )

    # ─────────────────────────────
    # Holdings
    # ─────────────────────────────
    holdings_evidence = []

    if any(k in ql for k in [
        "holdings", "portfolio",
        "allocation", "stocks",
        "invested in"
    ]):
        holdings_evidence.append("holdings_keyword")

    if holdings_evidence:
        add_op(
            "holdings_analysis",
            0.9,
            holdings_evidence
        )

    # Dedup
    dedup = {}
    for op in ops:
        dedup[op["type"]] = op

    return list(dedup.values())

# ══════════════════════════════════════════════════════════════════════════════
# 5. NODE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════


async def rewriter_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Decompose user query into 1-5 executable sub-tasks."""
    start_time = time.perf_counter()
    messages = state["messages"]
    user_query = messages[-1].content if messages else ""
    logger.info(f"Rewriter: '{user_query[:60]}...'")

    try:
        # Build context: system prompt + last 6 prior messages + current query
        prior_messages = messages[:-1][-6:]  # Up to 3 prior turns
        planner_msgs = [SystemMessage(content=QUERY_REWRITER_PROMPT)]
        planner_msgs.extend(prior_messages)

        # Consume ambiguity hint from intent_check FALLBACK path
        ambiguity_hint = state.get("shared_context", {}).get("_ambiguity_hint")
        if ambiguity_hint:
            logger.info(f"Rewriter: injecting ambiguity hint: {ambiguity_hint[:80]}")
            planner_msgs.append(SystemMessage(content=f"[PLANNER NOTE] {ambiguity_hint}"))

        planner_msgs.append(HumanMessage(content=f"User Query: {user_query}"))

        resolved_fund = state.get("shared_context", {}).get("_resolved_fund")
        if resolved_fund:
            msg = f"[PLANNER NOTE] Fund explicitly resolved by deterministic layer. Name: {resolved_fund['scheme_name']}, Code: {resolved_fund['scheme_code']}. DO NOT create a DISCOVERY task. Use this scheme_code directly for DATA/CALCULATOR/DOCUMENT tasks."
            planner_msgs.append(SystemMessage(content=msg))

        # method="function_calling" avoids strict additionalProperties enforcement
        planner = get_planner_llm().with_structured_output(QueryPlan, method="function_calling")
        plan: QueryPlan = await planner.ainvoke(planner_msgs, config=config)
        # Hard cap: max 5 tasks
        if len(plan.tasks) > 5:
            plan.tasks = plan.tasks[:5]

        # ── V3 Migration: Inject Operations ──
        # Extract workflow operations using deterministic rules
        features = _extract_features(user_query)
        extracted_ops = extract_operations(user_query, features)
        
        logger.info(f"OperationsExtracted: {extracted_ops}")

        # Inject operations into the planner's tasks
        for task in plan.tasks:
            task.operations = [Operation(**op) for op in extracted_ops]
            logger.info(f"TaskOperations: intent={task.intent}, operations={task.operations}")

        # Convert typed Entities to plain dict for shared_context
        entities_dict = {k: v for k, v in plan.entities.model_dump().items() if v is not None}
        
        duration = time.perf_counter() - start_time
        logger.info(f"Rewriter: {len(plan.tasks)} tasks, complexity={plan.complexity} (took {duration:.2f}s)")
        return {
            "query_plan": plan.model_dump(),
            "shared_context": entities_dict,
        }
    except Exception as e:
        logger.error(f"Rewriter failed: {e}")
        fallback = QueryPlan(
            tasks=[SubTask(id="task_1", intent=Intent.GENERAL, query=user_query, priority=1)],
            entities={},
            complexity="LOW",
        )
        duration = time.perf_counter() - start_time
        logger.info(f"Rewriter: fallback used (took {duration:.2f}s)")
        return {"query_plan": fallback.model_dump(), "shared_context": {}}


async def controller_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Validate plan, enforce guardrails, order tasks for execution."""
    start_time = time.perf_counter()
    plan = QueryPlan(**state["query_plan"])
    logger.info(f"Controller: {len(plan.tasks)} tasks, complexity={plan.complexity}")

    if plan.needs_clarification:
        return {"pending_tasks": [], "current_task_index": 0, "error": "clarification_needed"}

    tasks = list(plan.tasks)

    # ── Enforce Dependency Safety ──
    messages = state["messages"]
    user_query = messages[-1].content if messages else ""

    resolved_fund = state.get("shared_context", {}).get("_resolved_fund")
    has_scheme_code = bool(re.search(r'\b\d{5,6}\b', user_query)) or bool(resolved_fund)
    
    # Prune redundant DISCOVERY tasks if we already have a resolved fund
    if resolved_fund:
        pruned_ids = [t.id for t in tasks if t.intent == "DISCOVERY"]
        if pruned_ids:
            tasks = [t for t in tasks if t.id not in pruned_ids]
            # Clean up dependencies in remaining tasks
            for t in tasks:
                t.requires = [r for r in t.requires if r not in pruned_ids]
            logger.info(f"Controller: Pruned {len(pruned_ids)} redundant DISCOVERY tasks and cleaned dependencies.")

    has_discovery = any(t.intent == Intent.DISCOVERY for t in tasks)
    
    if not has_scheme_code and not has_discovery:
        needs_code = any(t.intent in [Intent.DATA, Intent.CALCULATOR, Intent.DOCUMENT] for t in tasks)
        if needs_code:
            logger.info("Controller: Enforcing DISCOVERY dependency because no scheme code was found.")
            disc_task = SubTask(
                id="task_forced_disc",
                intent=Intent.DISCOVERY,
                query=f"Find scheme code for: {user_query}",
                priority=1,
                requires=[]
            )
            for t in tasks:
                if t.intent in [Intent.DATA, Intent.CALCULATOR, Intent.DOCUMENT]:
                    t.requires.append("task_forced_disc")
            tasks.insert(0, disc_task)

    # Guardrail: max 5 agents executed (raised to accommodate forced DISCOVERY)
    if len(tasks) > 5:
        tasks = sorted(tasks, key=lambda t: t.priority)[:5]
        logger.warning("Controller: trimmed to 5 tasks")

    # Guardrail: max 1 DOCUMENT agent (expensive)
    doc_tasks = [t for t in tasks if t.intent == Intent.DOCUMENT]
    if len(doc_tasks) > 1:
        keep_id = doc_tasks[0].id
        tasks = [t for t in tasks if t.intent != Intent.DOCUMENT or t.id == keep_id]

    # Topological sort (respects dependencies, then priority)
    ordered = _topo_sort(tasks)
    
    for t in ordered:
        logger.info(
            f"ControllerTask: "
            f"intent={t.intent}, "
            f"operations={[o.type for o in t.operations]}"
        )
    
    duration = time.perf_counter() - start_time
    logger.info(f"Controller: executing {[t.intent for t in ordered]} (took {duration:.2f}s)")

    return {"pending_tasks": [t.model_dump() for t in ordered], "current_task_index": 0}


def _topo_sort(tasks: List[SubTask]) -> List[SubTask]:
    """Sort tasks respecting `requires` dependencies, then by priority.

    Includes cycle detection: if a circular dependency is found, the offending
    task is skipped with a log error rather than causing infinite recursion.
    """
    task_map = {t.id: t for t in tasks}
    visited: set = set()
    in_progress: set = set()  # tracks the current DFS path for cycle detection
    result: list = []

    def visit(tid: str) -> None:
        if tid in visited or tid not in task_map:
            return
        if tid in in_progress:
            logger.error(
                f"_topo_sort: cycle detected at task '{tid}' — skipping to prevent infinite recursion"
            )
            return
        in_progress.add(tid)
        for dep in task_map[tid].requires:
            visit(dep)
        in_progress.discard(tid)
        visited.add(tid)
        result.append(task_map[tid])

    for t in sorted(tasks, key=lambda x: x.priority):
        visit(t.id)
    return result


async def executor_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Run the current task's specialist agent with strict dependency enforcement."""
    start_time = time.perf_counter()
    pending = state["pending_tasks"]
    idx = state["current_task_index"]

    if idx >= len(pending):
        duration = time.perf_counter() - start_time
        logger.info(f"Executor: no pending tasks (took {duration:.2f}s)")
        return {"current_task_index": idx}

    task = SubTask(**pending[idx])
    operations = task.operations or []
    intent = task.intent
    logger.info(f"Executor: task '{task.id}' ({intent}): '{task.query[:50]}...'")

    # ── STAGE 1: PRE-CHECK — block if any dependency is missing or failed ──
    dep_data: dict = {}  # aggregated dependency outputs
    for dep_id in task.requires:
        dep = next((r for r in state.get("agent_results", []) if r.get("task_id") == dep_id), None)
        if dep is None or not dep.get("success"):
            error_detail = f"dependency '{dep_id}' {'failed' if dep else 'missing'}"
            logger.error(f"Executor: '{task.id}' blocked — {error_detail}")
            ar = AgentResult(
                task_id=task.id,
                intent=intent,
                answer="",
                confidence=0.0,
                success=False,
                error="dependency_failed",
            )
            duration = time.perf_counter() - start_time
            logger.info(f"Executor: '{task.id}' blocked (took {duration:.2f}s)")
            return {
                "current_task_index": idx + 1,
                "agent_results": [ar.model_dump()],
                "error": "dependency_failed",
            }
        dep_data[dep_id] = dep

    # ── STAGE 2: BUILD CONTEXT with structured dependency injection ──
    agent_msgs: list = list(state["messages"])
    ctx = state.get("shared_context", {})

    context_parts = []
    if ctx:
        context_parts.append(f"[Session context: {json.dumps(ctx)}]")
        if "_resolved_fund" in ctx:
            rf = ctx["_resolved_fund"]
            context_parts.append(f"[RESOLVED ENTITY]: The fund '{rf['scheme_name']}' has been resolved to scheme_code '{rf['scheme_code']}'. Use this code for all tool calls.")
        
        # New: Inject all resolved schemes from the mapping
        if "resolved_schemes" in ctx:
            schemes = ctx["resolved_schemes"]
            parts = [f"'{name}' (code: {code})" for code, name in schemes.items()]
            context_parts.append(f"[ALL RESOLVED ENTITIES]: {', '.join(parts)}. Use these codes for multi-fund analysis.")

    for dep_id, dep in dep_data.items():
        # Always inject the natural-language answer
        if dep.get("answer"):
            context_parts.append(f"[Result from {dep_id}]:\n{dep['answer']}")
        # Structured injection with hard constraint
        if dep.get("data"):
            block = "DEPENDENCY OUTPUT:\n"
            for k, v in dep["data"].items():
                block += f"- {k}: {v}\n"
            block += "\nRULE: You MUST use these exact values. Do not guess or override."
            context_parts.append(block)

    if context_parts:
        agent_msgs.append(SystemMessage(content="\n".join(context_parts)))

    if operations:
        op_lines = []

        for op in operations:
            op_lines.append(
                f"- {op.type} "
                f"(confidence={op.confidence}, "
                f"evidence={op.evidence})"
            )

        operation_prompt = f"""
CURRENT OPERATIONS:
{chr(10).join(op_lines)}

RULES:
- Only execute these operations.
- Avoid unrelated analysis.
- Prefer the minimum required tools.
- Do not perform speculative calculations.
"""

        agent_msgs.append(
            SystemMessage(content=operation_prompt)
        )

    agent_msgs.append(HumanMessage(content=task.query))

    # ── STAGE 3: EXECUTE ──
    answer, extracted, sources = await _run_agent(intent, agent_msgs, config, operations)

    # ── STAGE 4: POST-CHECK — verify dependency usage ──
    dep_scheme = None
    for dep in dep_data.values():
        if dep.get("data", {}).get("scheme_code"):
            dep_scheme = str(dep["data"]["scheme_code"])
            break

    post_violation = False
    if dep_scheme and intent in ("DATA", "CALCULATOR"):
        used_code = str(extracted.get("scheme_code", ""))
        if used_code != dep_scheme:
            logger.warning(f"Executor: POST-CHECK failed — expected scheme_code={dep_scheme}, got='{used_code}'")
            post_violation = True

    # ── STAGE 5: RETRY once on post-check violation ──
    if post_violation:
        logger.info(f"Executor: Retrying '{task.id}' with stronger instruction")
        retry_msgs = list(agent_msgs)  # copy
        retry_msgs.append(
            SystemMessage(
                content=(
                    f"RETRY: You previously failed to use the required dependency data.\n"
                    f"You MUST call the tool with scheme_code={dep_scheme}. This is mandatory."
                )
            )
        )
        answer, extracted, sources = await _run_agent(intent, retry_msgs, config, operations)

        used_code = str(extracted.get("scheme_code", ""))
        if used_code != dep_scheme:
            logger.error(f"Executor: '{task.id}' failed post-check after retry")
            ar = AgentResult(
                task_id=task.id,
                intent=intent,
                answer=answer,
                data=extracted,
                confidence=0.2,
                success=False,
                error="dependency_not_used",
            )
            return {
                "current_task_index": idx + 1,
                "agent_results": [ar.model_dump()],
                "error": "dependency_not_used",
            }

    # ── Build final result ──
    # Deep merge resolved_schemes to prevent losing previous funds
    new_schemes = extracted.get("resolved_schemes", {})
    existing_schemes = state.get("shared_context", {}).get("resolved_schemes", {})
    
    updated_ctx = {**state.get("shared_context", {}), **extracted}
    updated_ctx["resolved_schemes"] = {**existing_schemes, **new_schemes}
    
    success = bool(answer)
    if intent == "DATA" and not extracted:
        success = False

    ar = AgentResult(
        task_id=task.id,
        intent=intent,
        answer=answer,
        data=extracted,
        sources=sources,
        confidence=0.85 if answer else 0.3,
        success=success,
        error=None if success else "Agent produced no usable data",
    )
    duration = time.perf_counter() - start_time
    logger.info(
        f"Executor: '{task.id}' done. success={ar.success}, {len(answer)} chars, "
        f"shared_context keys={list(updated_ctx.keys())} (took {duration:.2f}s)"
    )
    # Log the full shared_context values for debugging
    try:
        logger.info(f"Executor: Current shared_context values: {json.dumps(updated_ctx, default=str)}")
    except Exception as e:
        logger.warning(f"Executor: Could not log shared_context: {e}")

    return {
        "current_task_index": idx + 1,
        "agent_results": [ar.model_dump()],
        "shared_context": updated_ctx,
        "sources": sources,
    }


def get_tools_for_operations(intent: str, operations: list) -> list:
    cfg = AGENT_CONFIG.get(intent, AGENT_CONFIG["GENERAL"])

    if not operations:
        return cfg["tools"]

    allowed = set()

    for op in operations:
        op_type = op["type"] if isinstance(op, dict) else op.type

        for tool_name in OPERATION_TOOL_MAP.get(op_type, []):
            allowed.add(tool_name)

    filtered = []

    for tool in cfg["tools"]:
        if tool.name in allowed:
            filtered.append(tool)

    return filtered or cfg["tools"]


async def _run_agent(intent: str, agent_msgs: list, config: RunnableConfig, operations: list = None) -> tuple[str, dict, list]:
    """Execute a specialist agent and extract answer, data, and sources."""
    try:
        tools = get_tools_for_operations(intent, operations or [])
        agent = create_react_agent(
            get_llm(),
            tools,
            prompt=AGENT_CONFIG[intent]["prompt"]
        )
        
        result = await agent.ainvoke({"messages": agent_msgs}, config=config)
        out_msgs = result.get("messages", [])

        # Extract final answer
        answer = ""
        for msg in reversed(out_msgs):
            if isinstance(msg, AIMessage) and msg.content:
                answer = msg.content
                break

        # Extract sources from tool messages
        sources = []
        for msg in out_msgs:
            if isinstance(msg, ToolMessage) and msg.name == "read_factsheet":
                try:
                    td = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    if isinstance(td, dict) and "sources" in td:
                        sources.extend(td["sources"])
                except (json.JSONDecodeError, TypeError):
                    pass

        extracted = _extract_tool_data(out_msgs)
        logger.info(f"Executor: '{intent}' agent finished. Extracted keys: {list(extracted.keys())}")
        if not extracted and intent == "DATA":
            logger.warning(f"Executor: 'DATA' agent produced no structured data. Raw answer: {answer[:100]}...")

        return answer, extracted, sources

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        return "", {}, []


def _extract_tool_data(messages: list) -> dict:
    """Extract structured data from tool messages for shared context."""
    data = {}
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        try:
            c = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            if not isinstance(c, dict):
                continue

            # Handle discovery tool outputs (keys are scheme codes)
            numeric_keys = [k for k in c.keys() if str(k).isdigit() and len(str(k)) >= 5]
            if numeric_keys:
                # Store all resolved schemes in a mapping
                if "resolved_schemes" not in data:
                    data["resolved_schemes"] = {}
                for k in numeric_keys:
                    data["resolved_schemes"][k] = c[k]
                
                # Maintain backward compatibility for single-fund flows
                if len(numeric_keys) == 1:
                    data["scheme_code"] = numeric_keys[0]
                    data["fund"] = c[numeric_keys[0]]

            # Handle standard structured outputs
            for key, field in [
                ("scheme_code", "scheme_code"),
                ("Scheme Code", "scheme_code"),
                ("nav", "nav"),
                ("Net Asset Value", "nav"),
                ("scheme_name", "fund"),
                ("Scheme Name", "fund"),
                ("fund_house", "amc"),
                ("Fund House", "amc"),
                ("date", "date"),
                ("Date", "date"),
                ("expense_ratio", "expense_ratio"),
                ("Expense Ratio", "expense_ratio"),
                ("exit_load", "exit_load"),
                ("Exit Load", "exit_load"),
                ("scheme_category", "category"),
                ("Scheme Category", "category"),
            ]:
                if key in c and c[key]:
                    data[field] = c[key]
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    
    if data:
        logger.debug(f"Extraction: successfully parsed {len(data)} fields: {list(data.keys())}")
    return data

# ──────────────────────────────────────────────────────────────────────────────
# SYNTHESIZER HELPERS
# ──────────────────────────────────────────────────────────────────────────────

_FOLLOWUP_KEYWORDS = {"why", "how", "explain", "details", "more", "which", "better", "compare", "analysis", "should"}
_REFERENCE_WORDS = {"this", "that", "it", "those"}


def _is_followup_query(messages: list) -> bool:
    """Return True if the latest user message looks like a follow-up.

    Conditions (any one triggers follow-up):
    1. Short message (≤6 words) preceded by an AI response
    2. Contains follow-up keywords (why, how, explain, ...)
    3. Contains reference words (this, that, it, those)
    """
    if len(messages) < 2:
        return False

    # The previous turn must be an AI message for this to be a follow-up
    prev = messages[-2]
    if not isinstance(prev, AIMessage):
        return False

    last = messages[-1]
    text = (last.content or "").strip().lower()
    words = text.split()

    if len(words) <= 6:
        return True
    if _FOLLOWUP_KEYWORDS & set(words):
        return True
    if _REFERENCE_WORDS & set(words):
        return True
    return False


def _auto_detect_mode(successful: list, results: list) -> str:
    """Determine response_mode from agent results alone (no follow-up logic)."""
    if len(successful) == 1 and successful[0]["intent"] == "DATA":
        if successful[0].get("data", {}).get("nav"):
            return "concise"
    if any(r["intent"] == "PERFORMANCE" for r in successful) or len(successful) > 1:
        return "analytical"
    return "detailed"


async def synthesizer_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Merge agent results into a final, mode-adaptive response."""
    start_time = time.perf_counter()
    results = state.get("agent_results", [])
    messages = state["messages"]
    user_query = messages[-1].content if messages else ""
    plan_dict = state.get("query_plan", {})

    logger.info(f"Synthesizer: merging {len(results)} results")

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    # ── Critical Data Guard ──
    if any(r.get("intent") == "DATA" and not r.get("data") for r in results):
        logger.warning("Synthesizer: DATA intent missing required data. Failing cleanly.")
        duration = time.perf_counter() - start_time
        logger.info(f"Synthesizer: failing due to missing data (took {duration:.2f}s)")
        return {
            "messages": [AIMessage(content="I couldn't retrieve the requested data. This can happen if the fund details are currently unavailable or the query was ambiguous. Please try with a specific fund name.")],
            "sources": [],
            "last_response_mode": state.get("last_response_mode"),
        }

    # ── Follow-up Detection ──
    is_followup = _is_followup_query(messages)
    prev_mode = state.get("last_response_mode")

    # ── Response Mode Selection ──
    if is_followup and prev_mode in ("concise", "analytical"):
        response_mode = "detailed"
        logger.info(f"Synthesizer: follow-up (prev={prev_mode}), upgrading to 'detailed'")
    else:
        response_mode = _auto_detect_mode(successful, results)
        logger.info(f"Synthesizer: using '{response_mode}' mode")

    # ── Concise Mode — deterministic, no LLM call ──
    if response_mode == "concise":
        r = successful[0]
        val = r["data"]["nav"]
        date = r["data"].get("date", "Latest")
        fund_name = (
            state.get("shared_context", {}).get("fund")
            or r["data"].get("fund", "Requested Fund")
        )
        if "Direct" not in fund_name and "Regular" not in fund_name:
            fund_name += " (Direct Growth)"

        ans = f"{fund_name}\n\nNAV: \u20b9{val}\nAs of: {date}\n\n_(Ask for details if needed)_"
        return {
            "messages": [AIMessage(content=ans)],
            "sources": r.get("sources", []),
            "last_response_mode": "concise",
        }

    # ── No successful results ──
    if not successful:
        fallback = "I wasn't able to find that information. Could you rephrase or provide more details?"
        if failed:
            errors = [r.get("error", "Unknown") for r in failed if r.get("error")]
            if errors:
                fallback += f"\n\n_(Errors: {'; '.join(errors)})_"
        return {
            "messages": [AIMessage(content=fallback)],
            "sources": [],
            "last_response_mode": response_mode,
        }

    # ── Analytical / Detailed Mode — LLM synthesis ──
    try:
        agent_outputs_text = ""
        all_sources = []
        for r in results:
            status = "✓" if r.get("success") else "✗"
            agent_outputs_text += f"\n--- [{status}] {r['intent']} (task: {r['task_id']}) ---\n"
            agent_outputs_text += r.get("answer", "(no output)") + "\n"
            all_sources.extend(r.get("sources", []))

        # Append follow-up instruction to system prompt
        followup_note = (
            "\n\nIMPORTANT: This is a follow-up question. Expand on the previous answer using context."
            if is_followup
            else ""
        )

        synth_prompt = SYNTHESIZER_PROMPT.format(
            user_query=user_query,
            complexity=plan_dict.get("complexity", "MEDIUM"),
            response_mode=response_mode,
            agent_outputs=agent_outputs_text,
        ) + followup_note

        # Build message list — inject prior AI turn for follow-up context
        synth_msgs: list = [SystemMessage(content=synth_prompt)]
        if is_followup and len(messages) >= 2 and isinstance(messages[-2], AIMessage):
            synth_msgs.append(AIMessage(content=f"[Previous answer]:\n{messages[-2].content}"))
        synth_msgs.append(
            HumanMessage(content=f"Original question: {user_query}\n\nSynthesize the above into a clear answer.")
        )

        response = await get_llm().ainvoke(synth_msgs, config=config)
        
        duration = time.perf_counter() - start_time
        logger.info(f"Synthesizer: response generated (took {duration:.2f}s)")
        
        return {
            "messages": [AIMessage(content=response.content)],
            "sources": all_sources,
            "last_response_mode": response_mode,
        }

    except Exception as e:
        logger.error(f"Synthesizer LLM failed: {e}")
        combined = "\n\n---\n\n".join(r["answer"] for r in successful if r.get("answer"))
        return {
            "messages": [AIMessage(content=combined or "Unable to synthesize.")],
            "sources": [],
            "last_response_mode": response_mode,
        }


async def _detect_intent_hybrid(q: str, config: RunnableConfig) -> str:
    ql = q.lower()
    # 1. High-confidence deterministic rules
    if any(k in ql for k in ["nav", "current price", "unit price"]):
        return "DATA"
    if any(k in ql for k in ["sip", "xirr", "calculate", "corpus", "future value", "projection", "how much will i get"]):
        return "CALCULATOR"
    if any(k in ql for k in ["factsheet", "holdings", "manager", "objective", "strategy", "invests in"]):
        return "DOCUMENT"
    if any(k in ql for k in ["best", "top", "compare", "vs", "better", "returns", "performance", "cagr"]):
        return "PERFORMANCE"

    # 2. LLM fallback for semantics
    try:
        classifier = get_planner_llm().with_structured_output(_IntentClass, method="function_calling")
        res = await classifier.ainvoke(
            [
                SystemMessage(
                    content="Classify the mutual fund query intent: DATA (nav/price), PERFORMANCE (best/compare/returns), DISCOVERY (search/list), DOCUMENT (holdings/strategy), CALCULATOR (sip maths), GENERAL (chitchat/basics)."
                ),
                HumanMessage(content=q),
            ],
            config=config
        )
        return res.intent
    except Exception:
        return "GENERAL"


def _has_fund_entity(q: str) -> bool:
    ql = q.lower()
    known = ["sbi", "hdfc", "icici", "axis", "parag", "ppfas", "nippon", "quant"]
    return any(k in ql for k in known) or any(w.isdigit() and len(w) >= 4 for w in q.split())


def _has_category(q: str) -> bool:
    ql = q.lower()
    return any(c in ql for c in CATEGORIES)




def _extract_features(q: str) -> dict:
    ql = q.lower()
    return {
        "has_fund": _has_fund_entity(q),
        "has_category": _has_category(q),
        "has_amount": "₹" in q or bool(re.search(r"\d", q)),
        "has_tenure": any(k in ql for k in ["year", "month", "yr", "years", "months"]),
        "has_return_rate": any(k in ql for k in ["%", "return", "interest", "cagr", "rate"]),
        "has_risk": any(k in ql for k in ["risk", "safe", "aggressive", "conservative", "stable", "growth"]),
        "is_comparative": any(k in ql for k in ["best", "top", "compare", "better", "vs", "good"]),
        "is_short": len(ql.split()) <= 4,
    }


def _compute_completeness(intent: str, features: dict) -> tuple[float, List[str]]:
    reqs = INTENT_REQUIREMENTS.get(intent, [])
    present = 0
    missing = []

    for r in reqs:
        ok = False
        if r == "fund":
            ok = features["has_fund"]
        elif r == "category_or_fund":
            ok = features["has_fund"] or features["has_category"]
        elif r == "category":
            ok = features["has_category"]
        elif r == "amount":
            ok = features["has_amount"]
        elif r == "tenure":
            ok = features["has_tenure"]
        elif r == "horizon":
            ok = features["has_tenure"]
        elif r == "return_rate":
            ok = features["has_return_rate"]
        elif r == "risk":
            ok = features["has_risk"]

        if ok:
            present += 1
        else:
            missing.append(r)

    score = present / len(reqs) if reqs else 1.0
    return score, missing


def _compute_ambiguity(features: dict, completeness: float) -> float:
    # Only penalise comparative queries that lack fund/category context.
    # "Best large-cap funds for 5 years" has context — no penalty.
    has_context = features["has_fund"] or features["has_category"]
    keyword_penalty = 0.2 if features["is_comparative"] and not has_context else 0.0
    short_penalty = 0.2 if features["is_short"] else 0.0
    # lower completeness → higher ambiguity
    base = 1.0 - completeness
    return min(1.0, base + keyword_penalty + short_penalty)


def _decide(completeness: float, ambiguity: float) -> str:
    # tune these thresholds
    if completeness < 0.5 or ambiguity > 0.75:
        return "CLARIFY"
    elif completeness < 0.8:
        return "FALLBACK"
    else:
        return "EXECUTE"


async def intent_check_node(state: PipelineState, config: RunnableConfig) -> dict:
    start_time = time.perf_counter()
    messages = state["messages"]
    query = messages[-1].content if messages else ""

    # 1. extract features
    features = _extract_features(query)

    # 2. detect intent (hybrid)
    intent = await _detect_intent_hybrid(query, config)

    # ── Safety net: GENERAL intent bypasses full orchestration ──
    if intent == "GENERAL":
        logger.info("IntentCheck: GENERAL intent — injecting direct plan (safety net)")
        return {
            "intent_check": {
                "intent": "GENERAL",
                "confidence": 0.95,
                "completeness_score": 1.0,
                "ambiguity_score": 0.0,
                "missing_fields": [],
                "decision": "EXECUTE",
            },
            "query_plan": {
                "tasks": [
                    {
                        "id": "task_1",
                        "intent": "GENERAL",
                        "query": query,
                        "priority": 1,
                        "requires": [],
                    }
                ],
                "entities": {},
                "complexity": "LOW",
            },
        }

    # 3. compute completeness
    resolved_fund = state.get("shared_context", {}).get("_resolved_fund")
    if resolved_fund:
        # If we already resolved the fund, force completeness features for 'fund'
        features["has_fund"] = True
        logger.info("IntentCheck: Fund already resolved, boosting completeness features.")

    completeness, missing = _compute_completeness(intent, features)

    # 4. compute ambiguity
    ambiguity = _compute_ambiguity(features, completeness)

    # 4. decision
    decision = _decide(completeness, ambiguity)
    duration = time.perf_counter() - start_time
    logger.info(
        f"IntentCheck: query='{query[:60]}', intent={intent}, completeness={completeness:.2f}, ambiguity={ambiguity:.2f}, decision={decision} (took {duration:.2f}s)"
    )

    result = IntentCheckResult(
        intent=intent,
        confidence=round(max(0.0, min(1.0, completeness * (1.0 - ambiguity * 0.5))), 2),
        completeness_score=completeness,
        ambiguity_score=ambiguity,
        missing_fields=missing,
        decision=decision,
    )

    # 5. route outputs
    if decision == "CLARIFY":
        return {"intent_check": result.model_dump(), "error": "clarification_needed"}

    if decision == "FALLBACK":
        if intent == "PERFORMANCE":
            # Make the fallback assumption-aware so the synthesized answer reflects it
            category_name = "large-cap"
            if features["has_category"]:
                if "mid" in query.lower():
                    category_name = "mid-cap"
                elif "small" in query.lower():
                    category_name = "small-cap"
                elif "flexi" in query.lower():
                    category_name = "flexi-cap"

            fallback_query = (
                f"List top {category_name} mutual funds (Assuming moderate risk, long-term horizon for generic request)"
            )

            fallback_plan = {
                "tasks": [{"id": "task_1", "intent": intent, "query": fallback_query, "priority": 1, "requires": []}],
                "entities": {"category": category_name.replace("-cap", "_cap")},
                "complexity": "LOW",
            }

            return {"intent_check": result.model_dump(), "query_plan": fallback_plan}
        else:
            # If we don't have a specific fallback plan for this intent,
            # inject an ambiguity hint into shared_context so the rewriter
            # knows it is handling a partially-ambiguous query.
            hint = (
                f"Query is partially ambiguous (missing: {missing}). "
                "Use reasonable defaults and attempt to answer."
            )
            logger.info("IntentCheck: FALLBACK triggered, injecting ambiguity hint for rewriter.")
            return {
                "intent_check": result.model_dump(),
                "shared_context": {"_ambiguity_hint": hint},
            }

    # EXECUTE → go to rewriter
    return {"intent_check": result.model_dump()}


async def clarify_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Context-aware clarifier — dynamically builds targeted questions based on missing fields."""
    start_time = time.perf_counter()
    intent_check = state.get("intent_check") or {}

    intent = intent_check.get("intent", "GENERAL")
    missing = intent_check.get("missing_fields", [])

    logger.info(f"Clarify: intent={intent}, missing={missing}")

    # Fallback safety if nothing is marked missing or if it's a GENERAL intent fallback
    if not missing:
        plan_dict = state.get("query_plan") or {}
        rewriter_q = plan_dict.get("clarification_question")
        question = rewriter_q or DEFAULT_CLARIFICATION
        return {"messages": [AIMessage(content=question)], "sources": []}

    # Smart Shortcut: If only 1 field is missing, don't overcomplicate
    if len(missing) == 1:
        field = missing[0]
        meta = FIELD_QUESTIONS.get(field)
        if meta:
            response = f"{meta['q']}\n\nExample: *{meta['examples'][0]}*"
            # Optional Quick Choices for risk
            if intent == "PERFORMANCE" and field == "risk":
                response += "\n\n**Quick options:**\n- Low risk\n- Moderate risk\n- High risk"
            
            duration = time.perf_counter() - start_time
            logger.info(f"Clarify: targeted question generated (took {duration:.2f}s)")
            return {"messages": [AIMessage(content=response)], "sources": []}

    # Multiple missing fields: Build dynamic numbered list
    questions = []
    examples = []

    for field in missing:
        meta = FIELD_QUESTIONS.get(field)
        if not meta:
            continue
        questions.append(meta["q"])
        examples.extend(meta["examples"])

    # Limit to 3 questions max for UX
    questions = questions[:3]

    prefix = INTENT_PREFIX.get(intent, "I need more details,")
    response = f"{prefix} I need a bit more information:\n\n"

    for i, q in enumerate(questions, 1):
        response += f"{i}. {q}\n"

    # Quick Choices inject
    if intent == "PERFORMANCE" and "risk" in missing:
        response += "\n**Quick options for risk:**\n- Low risk\n- Moderate risk\n- High risk\n"

    if examples:
        response += "\n**Examples:**\n"
        # deduplicate examples and show up to 4
        seen = set()
        deduped = []
        for ex in examples:
            if ex not in seen:
                seen.add(ex)
                deduped.append(ex)
        for ex in deduped[:4]:
            response += f"- *{ex}*\n"

    duration = time.perf_counter() - start_time
    logger.info(f"Clarify: multi-field question generated (took {duration:.2f}s)")
    return {"messages": [AIMessage(content=response)], "sources": []}


# ══════════════════════════════════════════════════════════════════════════════
# 6. EDGE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════


def route_after_intent_check(state: PipelineState) -> str:
    """After intent check: clarify if ambiguous, else proceed to rewriter."""
    if state.get("error") == "clarification_needed":
        return "clarify"
    if state.get("query_plan"):  # fallback injected
        return "controller"
    return "rewriter"


def route_after_rewriter(state: PipelineState) -> str:
    """After rewriter: clarify if still vague, else proceed to controller."""
    plan = state.get("query_plan", {})
    if plan.get("needs_clarification"):
        return "clarify"
    return "controller"


def should_continue(state: PipelineState) -> str:
    """After executor: route to clarify on dependency failure, loop if more tasks, else synthesize."""
    MAX_TASKS = 5  # circuit-breaker: prevent infinite loops on dependency bugs
    error = state.get("error")
    if error in ("dependency_failed", "dependency_not_used"):
        logger.warning(f"Executor routing to clarify due to: {error}")
        return "clarify"
    idx = state.get("current_task_index", 0)
    pending = state.get("pending_tasks", [])
    if idx >= MAX_TASKS:
        logger.error(f"Executor: MAX_TASKS={MAX_TASKS} guard triggered, forcing synthesizer")
        return "synthesizer"
    if idx < len(pending):
        return "executor"
    return "synthesizer"


# ══════════════════════════════════════════════════════════════════════════════
# 7. BUILD THE GRAPH
# ══════════════════════════════════════════════════════════════════════════════


# ── Global checkpointer setup ──
_pool = None
_memory_saver = None

def get_checkpointer():
    global _pool, _memory_saver
    if _memory_saver is None:
        from app.db.connection import DATABASE_URL
        pg_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        
        _pool = AsyncConnectionPool(
            conninfo=pg_url,
            max_size=20,
            kwargs={"autocommit": True, "prepare_threshold": 0},
        )
        _memory_saver = AsyncPostgresSaver(_pool)
    return _memory_saver

def build_pipeline():
    """Build the v3 agentic pipeline graph.

    Topology:
        START → intent_check → clarify → END
                            ↘ rewriter → controller → executor ⟲ → synthesizer → END
                                       ↘ clarify → END
    """
    logger.info("Building v3 agentic pipeline")
    g = StateGraph(PipelineState)

    g.add_node("intent_check", intent_check_node)
    g.add_node("rewriter", rewriter_node)
    g.add_node("controller", controller_node)
    g.add_node("executor", executor_node)
    g.add_node("synthesizer", synthesizer_node)
    g.add_node("clarify", clarify_node)

    g.add_edge(START, "intent_check")
    g.add_conditional_edges(
        "intent_check",
        route_after_intent_check,
        {"clarify": "clarify", "rewriter": "rewriter", "controller": "controller"},
    )
    g.add_conditional_edges("rewriter", route_after_rewriter, {"clarify": "clarify", "controller": "controller"})
    g.add_edge("controller", "executor")
    g.add_conditional_edges(
        "executor",
        should_continue,
        {"executor": "executor", "synthesizer": "synthesizer", "clarify": "clarify"},
    )
    g.add_edge("synthesizer", END)
    g.add_edge("clarify", END)

    checkpointer = get_checkpointer()
    return g.compile(checkpointer=checkpointer)

async def setup_checkpointer():
    """Called during app startup to create LangGraph tables."""
    memory = get_checkpointer()
    await memory.setup()
    
def _warm_agent_cache() -> None:
    """Pre-create all ReAct agents at startup to avoid async race conditions."""
    for intent in AGENT_CONFIG:
        _get_agent(intent)
    logger.info(f"Agent cache warmed: {list(_cached_agents.keys())}")


_graph_instance = None


def get_pipeline():
    """Get or create the compiled pipeline graph."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_pipeline()
        _warm_agent_cache()
    return _graph_instance


# ══════════════════════════════════════════════════════════════════════════════
# 8. HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def _build_messages(user_input: str, chat_history: List[BaseMessage] = None) -> List[BaseMessage]:
    """Build message list from user input and optional chat history.

    CONTRACT: For follow-up detection to work, chat_history must include the
    preceding AIMessage from the last pipeline response as its final element.
    """
    messages = []
    if chat_history:
        for msg in chat_history:
            if isinstance(msg, (HumanMessage, AIMessage)):
                messages.append(msg)
        # Defensive: warn if follow-up detection will be blind
        if messages and not isinstance(messages[-1], AIMessage):
            logger.warning(
                "_build_messages: chat_history does not end with AIMessage "
                "— follow-up detection disabled for this request"
            )
    messages.append(HumanMessage(content=user_input))
    return messages


def _initial_state(messages: List[BaseMessage], last_response_mode: Optional[str] = None, initial_context: dict = None) -> dict:
    """Build the initial PipelineState dict for graph invocation."""
    return {
        "messages": messages,
        "intent_check": None,
        "query_plan": None,
        "shared_context": initial_context or {},
        "pending_tasks": [],
        "current_task_index": 0,
        "agent_results": [],
        "sources": [],
        "error": None,
        "last_response_mode": last_response_mode,
    }


def _extract_final_output(messages: List[BaseMessage]) -> str:
    """Extract the final AI response from message list."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return ""


def _dedup_sources(sources: list) -> list:
    """Deduplicate sources by URL, falling back to title or string repr."""
    seen: set = set()
    out: list = []
    for s in sources:
        key = s.get("url") or s.get("title") or str(s)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def _get_langfuse_config(session_id: str = None, user_id: str = None) -> dict:
    """Build config dict with Langfuse callback if available."""
    if _langfuse_available:
        try:
            handler = LangfuseHandler(session_id=session_id, user_id=user_id)
            return {"callbacks": [handler]}
        except Exception:
            pass
    return {}


# ══════════════════════════════════════════════════════════════════════════════
# 9. MAIN RUNNER FUNCTIONS (FastAPI entrypoints)
# ══════════════════════════════════════════════════════════════════════════════


async def run_agent_query(
    user_input: str,
    last_response_mode: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """
    Run a query through the agentic pipeline (non-streaming).

    Returns:
        dict with 'output', 'sources', 'route', 'pipeline_meta', 'error'.
    """
    # ── ROUTING LAYER ──────────────────────────────────────────────────────────
    route_type, lightweight_res = await route_message(user_input)

    if route_type in ("static", "no_tool"):
        logger.info(f"Query handled by router ({route_type}). Bypassing graph.")
        return {
            "output": lightweight_res,
            "sources": [],
            "route": route_type.upper(),
            "pipeline_meta": {
                "route": route_type,
                "pipeline_invoked": False,
                "tasks_run": 0,
                "clarified": False,
                "response_mode": "router",
                "complexity": "LOW",
            },
            "routing_meta": {
                "route": route_type,
                "pipeline_invoked": False,
            },
            "error": False,
        }

    # ── FUND RESOLVER LAYER ────────────────────────────────────────────────────
    resolver_res = resolve_fund(user_input)
    initial_context = {}
    if resolver_res.resolved and resolver_res.best_match:
        initial_context["_resolved_fund"] = {
            "scheme_code": resolver_res.best_match.scheme_code,
            "scheme_name": resolver_res.best_match.scheme_name,
        }

    # ── GRAPH EXECUTION ────────────────────────────────────────────────────────
    logger.info(f"Running query: '{user_input[:50]}...'")
    graph = get_pipeline()
    config = _get_langfuse_config(session_id=session_id)

    try:
        config["configurable"] = {"thread_id": session_id or "default_session"}
        payload = {
            "messages": [HumanMessage(content=user_input)],
            "intent_check": None,
            "query_plan": None,
            "shared_context": initial_context or {},  # Reset explicitly to avoid bleed
            "pending_tasks": [],
            "current_task_index": 0,
            "agent_results": None,  # triggers clear
            "sources": [],
            "error": None,
            "last_response_mode": last_response_mode,
        }

        result = await graph.ainvoke(payload, config=config)

        final_output = _extract_final_output(result["messages"])
        plan = result.get("query_plan", {})
        tasks = plan.get("tasks", []) if plan else []
        route = tasks[0]["intent"] if tasks else "GENERAL"
        sources = _dedup_sources(result.get("sources", []))

        logger.info(f"Query complete. Route: {route}, Output: {len(final_output)} chars")

        return {
            "output": final_output,
            "sources": sources,
            "route": route,
            "pipeline_meta": {
                "route": "tool",
                "pipeline_invoked": True,
                "tasks_run": len(result.get("agent_results", [])),
                "clarified": result.get("error") == "clarification_needed",
                "response_mode": result.get("last_response_mode"),
                "complexity": plan.get("complexity") if plan else None,
            },
            "routing_meta": {
                "route": "tool",
                "pipeline_invoked": True,
            },
            "error": False,
        }

    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}", exc_info=True)
        return {
            "output": "I encountered an error processing your request. Please try again.",
            "sources": [],
            "route": "ERROR",
            "pipeline_meta": {"tasks_run": 0, "clarified": False, "response_mode": None, "complexity": None},
            "routing_meta": {"route": "error", "pipeline_invoked": True},
            "error": True,
        }


async def _rebuild_context_from_checkpoint(session_id: str, user_input: str) -> RouteContext:
    """Peek at checkpoint state to get last fund/entity for routing context.

    This is NOT a full state restore — it's a lightweight read of just the
    shared_context from the last checkpoint, used only to make the routing
    decision smarter.
    """
    try:
        checkpointer = get_checkpointer()
        config = {"configurable": {"thread_id": session_id}}

        # Read the latest checkpoint without running any nodes
        checkpoint = await checkpointer.aget_tuple(config)
        if checkpoint and checkpoint.checkpoint:
            state = checkpoint.checkpoint.get("channel_values", {})
            shared_ctx = state.get("shared_context", {})

            resolved = shared_ctx.get("_resolved_fund")
            if resolved:
                return RouteContext(
                    last_fund_name=resolved.get("scheme_name"),
                    last_fund_code=resolved.get("scheme_code"),
                    last_response_mode=state.get("last_response_mode"),
                    last_intent=None,  # not explicitly stored separately in state
                    turn_count=2,      # we know it's at least turn 2
                )
    except Exception as e:
        logger.debug(f"Could not read checkpoint for routing context: {e}")

    return RouteContext()


async def stream_agent_query(
    user_input: str,
    last_response_mode: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """
    Stream a query through the agentic pipeline.
    Yields typed event dicts for frontend consumption.

    Strategy: emit node_start + tool events from executor,
    stream tokens only from synthesizer (the user-facing output).
    """
    logger.info(f"Streaming query: '{user_input[:50]}...'")

    # ── ROUTING LAYER ──────────────────────────────────────────────────────────
    # Build route context for the session
    route_context = RouteContext(last_response_mode=last_response_mode)
    
    # 1. Deterministic check (current query mentions a fund)
    resolver_res = resolve_fund(user_input)
    if resolver_res.resolved and resolver_res.best_match:
        route_context.last_fund_name = resolver_res.best_match.scheme_name
        route_context.last_fund_code = resolver_res.best_match.scheme_code
    
    # 2. Checkpoint check (previous turn mentioned a fund)
    if not route_context.last_fund_name and session_id:
        route_context = await _rebuild_context_from_checkpoint(session_id, user_input)

    # 3. Decision
    route_type, lightweight_res = await route_message(user_input, context=route_context)

    if route_type in ("static", "no_tool"):
        logger.info(f"Query handled by router ({route_type}). Bypassing graph.")
        # Yield metadata immediately
        yield {
            "type": "node_start",
            "node": "router",
            "display": "Responding",
        }
        
        if route_type == "static" or lightweight_res:
            # Stream the response back in chunks (deterministic or static)
            yield {
                "type": "token",
                "content": lightweight_res,
                "node": "router",
            }
        else:
            async for word in stream_no_tool_response(user_input, context=route_context):
                yield {
                    "type": "token",
                    "content": word,
                    "node": "router",
                }

        yield {
            "type": "done",
            "sources": [],
            "node": "router",
            "pipeline_meta": {
                "route": route_type,
                "pipeline_invoked": False,
                "tasks_run": 0,
                "clarified": False,
                "response_mode": "router",
                "complexity": "LOW",
            },
            "routing_meta": {
                "route": route_type,
                "pipeline_invoked": False,
            },
        }
        return

    # ── FUND RESOLVER LAYER ────────────────────────────────────────────────────
    config = _get_langfuse_config(session_id=session_id)
    config["configurable"] = {"thread_id": session_id or "default_session"}
    graph = get_pipeline()
    
    # Check if we already have a resolved fund in the session state
    existing_resolved_fund = None
    try:
        state_snapshot = await graph.aget_state(config)
        if state_snapshot.values:
            existing_resolved_fund = state_snapshot.values.get("shared_context", {}).get("_resolved_fund")
    except Exception as e:
        logger.warning(f"Could not fetch existing state for fund resolution check: {e}")

    initial_context = {}
    if not existing_resolved_fund:
        # We might have already resolved it in the routing layer above
        if route_context.last_fund_name and route_context.last_fund_code:
             initial_context["_resolved_fund"] = {
                "scheme_code": route_context.last_fund_code,
                "scheme_name": route_context.last_fund_name,
            }
        else:
            resolver_res = resolve_fund(user_input)
            if resolver_res.resolved and resolver_res.best_match:
                logger.info(f"Resolver: New fund resolved for session {session_id}: {resolver_res.best_match.scheme_name}")
                initial_context["_resolved_fund"] = {
                    "scheme_code": resolver_res.best_match.scheme_code,
                    "scheme_name": resolver_res.best_match.scheme_name,
                }
    else:
        logger.info(f"Resolver: Using existing resolved fund for session {session_id}")

    # ── GRAPH EXECUTION ────────────────────────────────────────────────────────
    PIPELINE_NODES = {"intent_check", "rewriter", "controller", "executor", "synthesizer", "clarify"}
    DISPLAY_NAMES = {
        "intent_check": "Analyzing",
        "rewriter": "Planning",
        "controller": "Preparing",
        "executor": "Working",
        "synthesizer": "Synthesizing",
        "clarify": "Clarifying",
    }

    try:
        current_node = None
        accumulated_sources = []
        tokens_emitted_nodes: set = set()  # track per-node to allow independent passthroughs
        final_state: dict = {}

        # Detect capability for state injection
        requested_capability = detect_requested_capability(user_input)

        config["configurable"] = {"thread_id": session_id or "default_session"}
        payload = {
            "messages": [HumanMessage(content=user_input)],
            "intent_check": None,
            "query_plan": None,
            "shared_context": initial_context,  # Merged with existing state by reducer
            "pending_tasks": [],
            "current_task_index": 0,
            "agent_results": None,  # triggers clear
            "sources": [],
            "error": None,
            "last_response_mode": last_response_mode,
            "requested_capability": requested_capability,
        }

        async for event in graph.astream_events(
            payload,
            config=config,
            version="v2",
        ):
            kind = event["event"]
            name = event.get("name", "")

            # Capture final state for pipeline_meta
            if kind == "on_chain_end" and name == "LangGraph":
                final_state = event["data"].get("output", {})

            # Node transitions
            if kind == "on_chain_start" and name in PIPELINE_NODES:
                if name != current_node:
                    current_node = name
                    yield {
                        "type": "node_start",
                        "node": name,
                        "display": DISPLAY_NAMES.get(name, name),
                    }

            # Stream tokens ONLY from synthesizer/clarify (user-facing output)
            elif kind == "on_chat_model_stream":
                if current_node not in ("synthesizer", "clarify"):
                    continue
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    tokens_emitted_nodes.add(current_node)
                    yield {
                        "type": "token",
                        "content": chunk.content,
                        "node": current_node,
                    }

            # Synthesizer passthrough: concise/guard modes skip LLM → emit content directly
            elif kind == "on_chain_end" and name == "synthesizer":
                if "synthesizer" not in tokens_emitted_nodes:
                    output = event["data"].get("output", {})
                    msgs = output.get("messages", [])
                    for msg in msgs:
                        content = getattr(msg, "content", None)
                        if content:
                            yield {"type": "token", "content": content, "node": "synthesizer"}
                            break

            # Clarify passthrough: static return, no LLM → emit content directly
            elif kind == "on_chain_end" and name == "clarify":
                if "clarify" not in tokens_emitted_nodes:
                    output = event["data"].get("output", {})
                    msgs = output.get("messages", [])
                    for msg in msgs:
                        content = getattr(msg, "content", None)
                        if content:
                            yield {"type": "token", "content": content, "node": "clarify"}
                            break

            # Tool events from executor
            elif kind == "on_tool_start" and current_node == "executor":
                yield {"type": "tool_start", "tool": name, "node": "executor"}

            elif kind == "on_tool_end" and current_node == "executor":
                tool_output = event["data"].get("output", {})
                if name == "read_factsheet" and isinstance(tool_output, dict):
                    if "sources" in tool_output:
                        accumulated_sources.extend(tool_output["sources"])
                yield {
                    "type": "tool_end",
                    "tool": name,
                    "success": not isinstance(tool_output, dict) or "error" not in tool_output,
                    "node": "executor",
                }

            # Graph completion
            elif kind == "on_chain_end" and name == "LangGraph":
                plan = final_state.get("query_plan") or {}
                yield {
                    "type": "done",
                    "sources": _dedup_sources(accumulated_sources),
                    "node": current_node,
                    "pipeline_meta": {
                        "route": "tool",
                        "pipeline_invoked": True,
                        "tasks_run": len(final_state.get("agent_results", [])),
                        "clarified": final_state.get("error") == "clarification_needed",
                        "response_mode": final_state.get("last_response_mode"),
                        "complexity": plan.get("complexity") if plan else None,
                    },
                    "routing_meta": {
                        "route": "tool",
                        "pipeline_invoked": True,
                    },
                }

    except Exception as e:
        logger.error(f"Streaming error: {str(e)}", exc_info=True)
        yield {
            "type": "error",
            "message": "I encountered an error while processing your request. Please try again or rephrase your question."
        }
