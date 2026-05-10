from dotenv import load_dotenv

# Load env before importing anything else
load_dotenv()

from langchain_core.messages import HumanMessage  # noqa: E402
from langfuse.callback import CallbackHandler  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.llm_clients import get_llm_with_fallbacks  # noqa: E402


def test_langfuse_tracing():
    print("Initializing Langfuse Callback Handler...")
    try:
        langfuse_handler = CallbackHandler()
        print("Langfuse handler initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize Langfuse handler: {e}")
        return

    print(f"Initializing LLM: {settings.LLM_MODEL}...")
    llm = get_llm_with_fallbacks(settings.LLM_MODEL, streaming=False)
    
    print("Invoking LLM with Langfuse callback...")
    try:
        response = llm.invoke(
            [HumanMessage(content="Hello! Please reply with 'Tracing works!' if you receive this.")],
            config={"callbacks": [langfuse_handler]}
        )
        print("\n--- LLM Response ---")
        print(response.content)
        print("--------------------\n")
        
        # Ensure traces are flushed to Langfuse
        print("Flushing traces to Langfuse...")
        langfuse_handler.auth_check()
        langfuse_handler.langfuse.flush()
        print("Success! Check your Langfuse dashboard to verify the trace.")
        
    except Exception as e:
        print(f"Error during LLM invocation or tracing: {e}")

if __name__ == "__main__":
    test_langfuse_tracing()
