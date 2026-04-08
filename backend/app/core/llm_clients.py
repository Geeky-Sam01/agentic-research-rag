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

def get_llm_with_fallbacks(primary_model: str, streaming: bool = False) -> ChatOpenAI:
    fallback_models = [
        "openrouter/auto",
        "openrouter/free"
    ]

    primary = make_llm(primary_model, streaming)
    fallbacks = [make_llm(m, streaming) for m in fallback_models]

    return primary.with_fallbacks(fallbacks)
