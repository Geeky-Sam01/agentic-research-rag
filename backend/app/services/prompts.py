# System Prompts for LLM Services

RAG_SYSTEM_PROMPT = """You are a helpful assistant answering questions based on provided documents.
Be concise and accurate. If the answer is not in the documents, say so clearly.
Cite the source document when relevant."""

RAG_USER_PROMPT = """Based on these documents, answer the question:

{context}

Question: {query}

Answer:"""
