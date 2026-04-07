Good question. Here's how you'd refactor your `llm.py` to use LangChain while keeping your existing fallback logic and streaming behavior.

---

### What LangChain replaces in your current code

| Current (`llm.py`) | LangChain equivalent |
|---|---|
| Raw `httpx` POST | `ChatOpenAI` pointed at OpenRouter |
| Manual prompt strings | `ChatPromptTemplate` |
| `json.loads()` parsing | `PydanticOutputParser` / `JsonOutputParser` |
| Manual fallback loop | `with_fallbacks()` |
| Manual SSE streaming | `.astream()` |

---

### Step 1 — Install dependencies

```bash
pip install langchain langchain-openai langchain-core
```

---

### Step 2 — LangChain client setup

LangChain's `ChatOpenAI` accepts a `base_url` and `api_key`, which is exactly how OpenRouter works:

```python
# app/core/llm_clients.py
from langchain_openai import ChatOpenAI
from app.core.config import settings

def make_llm(model: str, streaming: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.3,
        max_tokens=1024,
        streaming=streaming,
        default_headers={
            "HTTP-Referer": "http://localhost:4200",
            "X-OpenRouter-Title": "Agentic RAG"
        }
    )

# Your fallback chain — mirrors your models_to_try list
def get_llm_with_fallbacks(primary_model: str, streaming: bool = False) -> ChatOpenAI:
    fallback_models = [
        "qwen/qwen-turbo:free",
        "nvidia/nemotron-4-340b-instruct:free",
        "minimax/minimax-01:free",
        "google/gemma-2-9b-it:free"
    ]

    primary = make_llm(primary_model, streaming)
    fallbacks = [make_llm(m, streaming) for m in fallback_models]

    # LangChain's with_fallbacks handles 429s and exceptions automatically
    return primary.with_fallbacks(fallbacks)
```

---

### Step 3 — Prompts with LangChain templates

```python
# app/services/prompts.py
from langchain_core.prompts import ChatPromptTemplate

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a precise document Q&A assistant.
You MUST respond in valid JSON only. No markdown, no extra text.

Choose response type based on query:
- "table"   → comparative/multi-attribute data
- "cards"   → distinct concepts, steps, options  
- "summary" → overviews, definitions, quick answers
- "mixed"   → complex answers needing multiple formats

Schemas:
TABLE:   {{"type":"table","title":"...","headers":[...],"rows":[[...]]}}
CARDS:   {{"type":"cards","title":"...","cards":[{{"heading":"...","body":"...","tag":"..."}}]}}
SUMMARY: {{"type":"summary","headline":"...","key_points":[...],"conclusion":"..."}}
MIXED:   {{"type":"mixed","blocks":[{{"block_type":"summary|table|cards","content":{{...}}}}]}}
"""),
    ("human", "Context:\n{context}\n\nQuestion: {query}\n\nRespond ONLY with valid JSON.")
])
```

---

### Step 4 — Refactored `llm.py`

```python
# app/services/llm.py
import logging
import re
import json
from typing import AsyncGenerator, Optional

from langchain_core.output_parsers import JsonOutputParser
from app.core.llm_clients import get_llm_with_fallbacks
from app.services.prompts import RAG_PROMPT
from app.core.config import settings
from app.services.response_parser import parse_rag_response

logger = logging.getLogger(__name__)


async def generate_answer(query: str, context: str) -> dict:
    """Non-streaming: returns parsed structured response dict."""

    llm = get_llm_with_fallbacks(settings.LLM_MODEL, streaming=False)
    parser = JsonOutputParser()

    # LangChain LCEL chain: prompt | llm | parser
    chain = RAG_PROMPT | llm | parser

    try:
        result = await chain.ainvoke({"query": query, "context": context})
        return result  # Already a dict — pass to parse_rag_response if you want Pydantic
    except Exception as e:
        logger.error(f"LLM error: {str(e)}")
        raise


async def generate_answer_stream(
    query: str,
    context: str,
    model_override: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Streaming: yields text chunks, emits structured JSON at end."""

    primary = model_override if model_override else settings.LLM_MODEL
    llm = get_llm_with_fallbacks(primary, streaming=True)

    # For streaming, skip JsonOutputParser — it waits for full response
    # Use the raw chain and buffer manually
    chain = RAG_PROMPT | llm

    buffer = ""

    try:
        async for chunk in chain.astream({"query": query, "context": context}):
            # chunk is an AIMessageChunk — extract text content
            text = chunk.content
            if text:
                buffer += text
                yield text

        # Stream complete — now parse the full buffer
        cleaned = re.sub(r"```json|```", "", buffer).strip()
        try:
            data = json.loads(cleaned)
            parsed = parse_rag_response(data)
            # Emit structured sentinel for Angular to pick up
            yield f"\n\n__STRUCTURED__:{parsed.model_dump_json()}"
        except Exception as parse_err:
            logger.warning(f"Could not parse structured output: {parse_err}")
            # Fallback: emit as plain summary
            yield f'\n\n__STRUCTURED__:{{"type":"summary","headline":"Response","key_points":[{json.dumps(buffer)}]}}'

    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        yield f"ERROR: {str(e)}"
```

---

### What changed vs your original

```
Before:                          After:
─────────────────────────────    ─────────────────────────────
httpx.AsyncClient POST loop  →   chain.astream() / chain.ainvoke()
Manual 429 retry loop        →   .with_fallbacks() handles it
json.loads(raw_string)       →   JsonOutputParser or manual buffer parse
f-string prompt building     →   ChatPromptTemplate (typed, testable)
Hardcoded header injection   →   default_headers on ChatOpenAI client
```

---

### The full chain in one line

```python
chain = RAG_PROMPT | llm | JsonOutputParser()

# Invoke
result = await chain.ainvoke({"query": "...", "context": "..."})

# Stream
async for chunk in chain.astream({"query": "...", "context": "..."}):
    print(chunk)
```

This is standard **LCEL (LangChain Expression Language)** — the `|` pipe composes prompt → model → parser. It's also what makes swapping models, parsers, or prompts trivial later when you move to DockTalk.