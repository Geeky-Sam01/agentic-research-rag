"""Smoke tests — verify imports and config loading."""

"""TODO : Add more tests for RAG pipeline"""
import os  # noqa: E402

# Set required env vars before importing app modules
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("PORT", "8000")
os.environ.setdefault("HOST", "0.0.0.0")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("CORS_ORIGIN", "*")
os.environ.setdefault("INDEX_PATH", "/tmp/test_indices")
os.environ.setdefault("UPLOAD_PATH", "/tmp/test_uploads")
os.environ.setdefault("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
os.environ.setdefault("EMBEDDING_DIM", "384")
os.environ.setdefault("LLM_MODEL", "openrouter/free")


class TestConfig:
    def test_settings_loads(self):
        from app.core.config import Settings

        s = Settings()
        assert s.PORT == 8000
        assert s.EMBEDDING_DIM == 384
        assert s.LLM_MODEL == "openrouter/free"

    def test_settings_has_required_fields(self):
        from app.core.config import Settings

        s = Settings()
        assert s.OPENROUTER_API_KEY is not None
        assert s.HOST is not None
        assert s.CORS_ORIGIN is not None


class TestSchemas:
    def test_document_upload_response(self):
        from app.models.schemas import DocumentUploadResponse

        r = DocumentUploadResponse(
            success=True,
            message="ok",
            totalIndexed=10,
            chunksCreated=10,
            embeddingModel="test",
            embeddingDimension=384,
        )
        assert r.success is True
        assert r.totalIndexed == 10

    def test_query_request_defaults(self):
        from app.models.schemas import QueryRequest

        q = QueryRequest(query="test query")
        assert q.query == "test query"
        assert q.stream is True

    def test_finsight_response_fields(self):
        from app.models.schemas import FinSightResponse

        assert "blocks" in FinSightResponse.model_fields
        assert "query" in FinSightResponse.model_fields
        assert "intent" in FinSightResponse.model_fields

    def test_source_model(self):
        from app.models.schemas import Source

        s = Source(text="sample", source="file.pdf", similarity="0.92")
        assert s.source == "file.pdf"


class TestAgentToolsImport:
    def test_all_tools_import(self):
        from app.services.agent_tools import ALL_MF_TOOLS

        assert len(ALL_MF_TOOLS) == 9

    def test_tool_names_unique(self):
        from app.services.agent_tools import ALL_MF_TOOLS

        names = [t.name for t in ALL_MF_TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_tool_descriptions_not_empty(self):
        from app.services.agent_tools import ALL_MF_TOOLS

        for t in ALL_MF_TOOLS:
            assert t.description, f"Tool {t.name} has no description"


class TestPrompts:
    def test_system_prompt_exists(self):
        from app.services.prompts import MF_RESEARCH_SYSTEM_PROMPT

        assert isinstance(MF_RESEARCH_SYSTEM_PROMPT, str)
        assert len(MF_RESEARCH_SYSTEM_PROMPT) > 100

    def test_rag_stream_prompt_exists(self):
        from langchain_core.prompts import ChatPromptTemplate

        from app.services.prompts import RAG_STREAM_PROMPT

        assert isinstance(RAG_STREAM_PROMPT, ChatPromptTemplate)

    def test_rag_structured_prompt_exists(self):
        from langchain_core.prompts import ChatPromptTemplate

        from app.services.prompts import RAG_STRUCTURED_PROMPT

        assert isinstance(RAG_STRUCTURED_PROMPT, ChatPromptTemplate)
