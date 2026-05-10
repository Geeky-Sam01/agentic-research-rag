<div align="center">

# 🔍 FinSight: Agentic Financial Research RAG

[![CI Status](https://github.com/Geeky-Sam01/agentic-research-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/Geeky-Sam01/agentic-research-rag/actions/workflows/ci.yml)
[![Security Audit](https://img.shields.io/badge/Security-Audited-success?style=flat-square&logo=github-actions&logoColor=white)](https://github.com/Geeky-Sam01/agentic-research-rag/actions)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Angular](https://img.shields.io/badge/Frontend-Angular%2021-DD0031?style=flat-square&logo=angular&logoColor=white)](https://angular.io/)
[![LangChain](https://img.shields.io/badge/Agent-LangGraph-00ADFF?style=flat-square&logo=langchain&logoColor=white)](https://langchain.com/)
[![VectorDB](https://img.shields.io/badge/VectorDB-Qdrant-FF4B4B?style=flat-square&logo=qdrant&logoColor=white)](https://qdrant.tech/)

</div>

**FinSight** is an autonomous financial research assistant that combines deep document analysis with live market data retrieval. Built on a two-phase agentic pipeline, it doesn't just find information — it routes, resolves, researches, verifies, and synthesizes analytical answers.

---

## 🌟 Flagship Features

| Feature | Description |
|---|---|
| **🧭 3-Layer Smart Router** | Intercepts simple queries before they touch the graph — static regex, heuristic keywords, and a lightweight LLM classifier work in cascade to minimize latency. |
| **🛡️ Smart Fund Resolver** | A pre-graph semantic entity resolution layer that maps colloquial fund names and historical aliases to exact AMFI scheme codes via a 5-step matching cascade. |
| **🧠 6-Node LangGraph Pipeline** | Intent check → Rewriter → Controller → Executor loop → Synthesizer, with a dedicated Clarify node for ambiguous queries. |
| **📋 Structured Query Planner** | Decomposes complex financial queries into up to 5 typed, dependency-aware sub-tasks before execution. |
| **🔄 Operation-Centric Executor** | ReAct agents scoped to specific operations (nav_lookup, holdings_analysis, sip_projection, etc.) with dependency injection, post-check validation, and auto-retry. |
| **📈 SIP Simulation Engine** | Robust backtesting for historical SIP returns and CAGR-based future projections with yearly top-ups. |
| **📑 3-Layer PDF Engine** | High-fidelity extraction using `pdfplumber`, `PyMuPDF`, and `Tesseract OCR` fallback for scanned financial reports. |
| **📉 Mutual Fund Intelligence** | Live NAV quotes and historical performance tracking with a 5-day automated fallback mechanism. |
| **💾 Multi-Turn Memory** | PostgreSQL-backed checkpointing via LangGraph's `AsyncPostgresSaver` with lightweight checkpoint peeking for fast follow-up routing. |
| **⚡ Real-Time Thought Trace** | Transparent research logs showing tool calls and retrieval steps in a collapsible, persistent UI accordion. |
| **🔗 Deep Source Attribution** | Evidence panel that highlights and previews exact source chunks used in every response. |

---

## 🏗️ System Architecture

Every query is processed through two sequential phases. Most simple queries are resolved in Phase 1 and never reach the graph.

---

### Phase 1 — Pre-Graph Layer

Two lightweight systems run before the LangGraph pipeline is invoked.

#### 🧭 3-Layer Router (`router.py`)

Decides whether the agent graph is needed at all. Layers run in cascade — if any layer produces a high-confidence decision, the remaining layers are skipped entirely.

```mermaid
flowchart TD
    Q[User Query] --> SG

    subgraph L0["Layer 0 — Static Gate"]
        SG{"Greeting / FAQ\nregex match?"}
    end

    SG -- yes --> STATIC["Instant response\n(no LLM, no graph)"]
    SG -- no --> HR

    subgraph L1["Layer 1 — Heuristic Router"]
        HR{"Finance keywords\nor SIP / compare signal?"}
    end

    HR -- "NO_TOOL\n(no finance signal)" --> NO_TOOL["Direct response\n(no LLM, no graph)"]
    HR -- "TOOL\n(high confidence)" --> TOOL_EXIT["Proceed to\nFund Resolver"]
    HR -- ambiguous --> LC

    subgraph L2["Layer 2 — LLM Classifier"]
        LC{"Lightweight\nstructured-output LLM"}
    end

    LC -- NO_TOOL --> NO_TOOL_LLM["Direct response\n(single LLM call)"]
    LC -- TOOL --> TOOL_LLM["Proceed to\nFund Resolver"]

    style L0 fill:#0d47a1,color:#fff
    style L1 fill:#1b5e20,color:#fff
    style L2 fill:#b71c1c,color:#fff
```

Queries handled as `NO_TOOL` or `static` never reach the graph, keeping latency low for conversational and conceptual queries.

#### 🛡️ Smart Fund Resolver (`fund_resolver.py`)

When a query needs tool execution, the resolver attempts to map any fund name in the query to an exact 6-digit AMFI scheme code before the graph starts. The resolved code is injected into the initial graph state, preventing redundant DISCOVERY tasks.

Resolution runs as a 5-step cascade, stopping at the first confident match:

```mermaid
flowchart TD
    FN[Fund Name Input] --> S1

    subgraph S1["Step 1 — Alias Index"]
        A1{"70+ curated aliases\n(ppfas, nifty50, ...)"}
    end
    A1 -- match --> RESOLVED["Resolved scheme_code\ninjected into graph"]
    A1 -- no match --> S2

    subgraph S2["Step 2 — Exact Normalized"]
        A2{"Strip noise\nnormalize, lookup"}
    end
    A2 -- match --> RESOLVED
    A2 -- no match --> S3

    subgraph S3["Step 3 — Prefix Match"]
        A3{"Scheme name starts\nwith query?"}
    end
    A3 -- match --> RESOLVED
    A3 -- no match --> S4

    subgraph S4["Step 4 — Token Match"]
        A4{"Tokenize + index\nintersection + coverage"}
    end
    A4 -- match --> RESOLVED
    A4 -- no match --> S5

    subgraph S5["Step 5 — Fuzzy Match"]
        A5{"difflib\nSequenceMatcher"}
    end
    A5 -- match --> RESOLVED
    A5 -- no match --> UNRESOLVED["Unresolved\ngraph runs DISCOVERY"]

    style S1 fill:#0d47a1,color:#fff
    style S2 fill:#1565c0,color:#fff
    style S3 fill:#1b5e20,color:#fff
    style S4 fill:#2e7d32,color:#fff
    style S5 fill:#388e3c,color:#fff
```

---

### Phase 2 — LangGraph Execution (6-Node Graph)

Queries that require live data, calculations, or document analysis run through a compiled LangGraph state machine with 6 nodes.

#### Full Graph Topology

```mermaid
graph TD
    A([User Query]) --> IC

    IC[Intent Check\nambiguity + completeness scoring]
    IC -- EXECUTE --> RW
    IC -- GENERAL skip rewriter --> CT
    IC -- CLARIFY --> CL

    RW[Rewriter\ndecompose into 1-5 sub-tasks]
    RW -- ok --> CT

    CT[Controller\nguardrails + topological sort]
    CT -- next task --> EX
    CT -- ambiguity detected --> CL
    CT -- all tasks done --> SY

    EX[Executor\nReAct specialist agent]
    EX -- result stored --> CT
    EX -- violation retry max 1 --> EX

    SY[Synthesizer\nmode-adaptive response fusion]
    SY --> END([END])

    CL[Clarify\ntargeted question generation]
    CL --> END([END])
```

#### Node Responsibilities

**`intent_check`**
Runs before the rewriter on every query. Extracts features (fund entity, category, amount, tenure), detects intent via a hybrid heuristic + LLM classifier, and computes completeness and ambiguity scores. Routes to `EXECUTE`, `GENERAL` (with a pre-built plan, skips rewriter), or `CLARIFY`.

**`rewriter`**
Calls a structured-output LLM planner to decompose the query into up to 5 typed `SubTask` objects. Each task has an intent (`DATA`, `PERFORMANCE`, `DISCOVERY`, `DOCUMENT`, `CALCULATOR`, `GENERAL`), a set of operations, a priority, and a `requires` dependency list. Enforces a hard cap of 5 tasks.

**`controller`**
Validates the task plan and enforces guardrails before execution:
- Prunes redundant `DISCOVERY` tasks if a fund was already pre-resolved
- Injects a forced `DISCOVERY` task if downstream tasks need a scheme code but none is available
- Caps execution at 5 total tasks
- Limits `DOCUMENT` tasks to 1 (expensive RAG operation)
- Runs a topological sort (with cycle detection) to order tasks by dependency, then priority

**`executor`** _(invoked once per task by the controller loop)_
Runs the correct ReAct specialist agent for each task in order. For every task:
1. **Pre-check** — blocks execution if any declared dependency failed
2. **Context injection** — builds a rich message list from shared state, resolved entities, and dependency outputs
3. **Agent execution** — runs the scoped ReAct agent with only the tools relevant to the task's operations
4. **Post-check** — verifies the agent actually used the required scheme code (for DATA/CALCULATOR tasks)
5. **Retry** — re-runs once with a stronger instruction if post-check fails (max 1 retry)

Results are accumulated into `agent_results` and `shared_context` for downstream tasks.

#### Specialist Agents

| Agent | Intent | Tools |
|---|---|---|
| DATA | nav_lookup, fund_info | get_scheme_quote, get_historical_nav, get_scheme_details |
| PERFORMANCE | returns_analysis, benchmark | get_equity_performance, get_debt_performance, get_hybrid_performance |
| DISCOVERY | fund_search | search_schemes, search_scheme_by_name |
| DOCUMENT | holdings, sector_alloc | read_factsheet (Qdrant RAG) |
| CALCULATOR | sip_projection | calculate_returns (NAV simulation) |
| GENERAL | conversational | None |

**`synthesizer`**
Merges all agent results into a single user-facing response. Selects a response mode automatically:
- `concise` — single NAV lookup, returned deterministically (no LLM call)
- `analytical` — multi-fund or performance query, LLM formats a Markdown table with key takeaways
- `detailed` — follow-up queries or complex multi-step results, full LLM synthesis with reasoning

Includes follow-up detection: if the current query is a short follow-up to a prior AI response, the mode upgrades to `detailed` automatically.

**`clarify`**
Generates targeted clarification questions from the `missing_fields` list produced by `intent_check`. Single missing field → one focused question with an example. Multiple missing fields → numbered list capped at 3 questions, with quick-choice options where applicable.

---

### Shared Context Layer

The `shared_context` dict flows through the entire graph and accumulates across executor iterations. It holds:

- `_resolved_fund` — pre-resolved scheme code from the Fund Resolver
- `resolved_schemes` — mapping of all scheme codes resolved during execution (supports multi-fund queries)
- `scheme_code`, `nav`, `fund`, `amc`, `date`, `category` — structured fields extracted from tool outputs
- `_ambiguity_hint` — injected by `intent_check` on GENERAL to guide the rewriter

---

### 💾 Multi-Turn Memory

Every graph invocation is checkpointed to PostgreSQL via `AsyncPostgresSaver`. Each conversation thread maintains a persistent `PipelineState` across turns, preserving messages, shared context, agent results, and the query plan.

On follow-up queries, the pre-graph router performs a lightweight checkpoint peek to recover `last_fund_name` and `last_fund_code` without a full state restore — making follow-up routing both fast and context-aware. The controller then merges the restored state with any new context, so queries like "How are its holdings?" resolve correctly without re-stating the fund name.

```mermaid
flowchart LR
    subgraph Q1["Query 1"]
        A1["NAV of HDFC Top 100"] --> B1["Executor stores\nfund_code in shared_context"]
    end

    subgraph Q2["Query 2 — Follow-up"]
        A2["How are its holdings?"]
        A2 --> B2["Router peeks checkpoint\nrecovers last_fund_code"]
        B2 --> C2["DOCUMENT Agent uses\nfund_code from state"]
    end

    subgraph DB["PostgreSQL — AsyncPostgresSaver"]
        CP["PipelineState:\nmessages, shared_context,\nagent_results, query_plan"]
    end

    Q1 -.->|checkpoint saved| DB
    DB -.->|state restored| Q2
    Q1 --> Q2

    style Q1 fill:#1b5e20,color:#fff
    style Q2 fill:#0d47a1,color:#fff
    style DB fill:#4a148c,color:#fff
```

---

### 📥 Document Ingestion Pipeline

```mermaid
graph LR
    A[Raw PDF] --> B[3-Layer Extraction]
    B --> C[pdfplumber: Text]
    B --> D[PyMuPDF: Layout]
    B --> E[OCR: Scanned Pages]
    C & D & E --> F[Contextual Chunking]
    F --> G[Sentence Transformers]
    G --> H[(Qdrant Vector DB)]
```

---

## 🖼️ Gallery

### 🖥️ 2-Pane Dashboard
The intuitive 2-pane interface separates the primary research chat from the context-aware knowledge sidebar.
<p align="center">
  <img src="assets/Screenshot 2026-04-08 032453.png" width="90%" border="1" />
</p>

### 🧠 Research Steps & 📊 Structured Analysis
Inspect the agent's real-time thought process or switch to "Explainer Mode" for highly structured tabular summaries.
<p align="center">
  <img src="assets/Screenshot 2026-04-08 032558.png" width="48%" />
  <img src="assets/Screenshot 2026-04-08 032910.png" width="48%" />
</p>

### 📚 Knowledge Library
Command center for document management, indexing status, and automated discovery.
<p align="center">
  <img src="assets/Screenshot 2026-04-08 032943.png" width="90%" />
</p>

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** — High-performance async API framework
- **LangGraph & LangChain** — Graph-based agent orchestration with state checkpointing via PostgreSQL
- **Qdrant** — High-performance vector database (local storage mode)
- **Sentence Transformers** — Local embedding generation (`all-MiniLM-L6-v2`)
- **pdfplumber / PyMuPDF / Tesseract** — 3-layer PDF extraction pipeline
- **Langfuse** — Optional observability and tracing

### Frontend
- **Angular 21** — Stateful SPA framework
- **Tailwind CSS v4** — Utility-first styling
- **PrimeNG** — Professional UI component library
- **IndexedDB** — Persistent local storage for chat history

---

## 🚀 Getting Started

### 1. Backend Setup
```bash
cd backend
uv sync
# Create .env with your OpenRouter API Key
python -m uvicorn app.main:app --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm start
```

---

> [!IMPORTANT]
> **FinSight** is built with a "Privacy First" mindset. All embeddings are generated locally, and your documents are stored in a private local Qdrant instance.
