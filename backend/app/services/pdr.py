from typing import List, Dict
from app.services.document_processor import chunk_text


def create_parent_chunks(
    text: str,
    parent_chunk_size: int = 1500,
    parent_overlap: int = 200
) -> List[str]:
    """
    Split document into large parent sections.
    """
    return chunk_text(text, chunk_size=parent_chunk_size, overlap=parent_overlap)


def create_child_chunks(
    parent_chunks: List[str],
    child_chunk_size: int = 400,
    child_overlap: int = 80
) -> List[Dict]:
    """
    Split each parent chunk into smaller chunks for embedding.
    Returns list containing chunk text + parent mapping.
    """

    children = []

    for parent_id, parent_text in enumerate(parent_chunks):

        small_chunks = chunk_text(
            parent_text,
            chunk_size=child_chunk_size,
            overlap=child_overlap
        )

        for chunk in small_chunks:
            children.append({
                "text": chunk,
                "parent_id": parent_id
            })

    return children


def build_pdr_structure(text: str):
    """
    Complete Parent Document Retrieval preprocessing.
    Returns:
        parent_chunks
        child_chunks_with_metadata
    """

    parent_chunks = create_parent_chunks(text)

    child_chunks = create_child_chunks(parent_chunks)

    return parent_chunks, child_chunks