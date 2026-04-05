from langchain_core.prompts import ChatPromptTemplate

# Streaming mode: Just raw answers, identical to what was there before
RAG_STREAM_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant answering questions based on provided documents.\nBe concise and accurate. If the answer is not in the documents, say so clearly.\nCite the source document when relevant."),
    ("human", "Based on these documents, answer the question:\n\n{context}\n\nQuestion: {query}\n\nAnswer:")
])

# Structured mode: Analytical extraction (Relies on LangChain with_structured_output to enforce JSON types)
RAG_STRUCTURED_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Extract structured financial insights from the context.

Use:
- metric blocks for numeric values
- table blocks for holdings
- summary blocks for explanations

Be accurate. Do not hallucinate."""),
    ("human", "Context:\n{context}\n\nQuestion: {query}")
])
