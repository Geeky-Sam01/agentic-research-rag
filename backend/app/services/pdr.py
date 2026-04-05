from typing import List, Dict, Tuple, Any, TypedDict, Optional


class ParentChunk(TypedDict):
    id: str
    page: Any
    heading: str
    text: str


class ChildChunk(TypedDict):
    text: str
    parent_id: str
    page: Any
    heading: str


def build_pdr_structure(
    structured_chunks: List[Dict[str, Any]]
) -> Tuple[List[ParentChunk], List[ChildChunk]]:
    """
    Builds Parent Document Retrieval structure from structured chunks.

    Input:
    [
        {
            "text": str,
            "page": int,
            "heading": str
        }
    ]

    Returns:
    parent_chunks: [
        {
            "id": str,
            "page": int,
            "heading": str,
            "text": str
        }
    ]

    child_chunks: [
        {
            "text": str,
            "parent_id": str,
            "page": int,
            "heading": str
        }
    ]
    """

    parent_map: Dict[str, str] = {}
    parent_chunks: List[ParentChunk] = []
    child_chunks: List[ChildChunk] = []


    for chunk in structured_chunks:
        page = chunk.get("page")
        heading = str(chunk.get("heading") or "General")
        text_str: str = str(chunk.get("text") or "")

        # Unique parent key
        key = f"{page}_{heading}"

        if key not in parent_map:
            p_id = f"parent_{len(parent_chunks)}"
            parent_map[key] = p_id

            parent_chunks.append({
                "id": p_id,
                "page": page,
                "heading": heading,
                "text": text_str
            })
        else:
            # Append text to existing parent
            p_id = parent_map[key]

            for p in parent_chunks:
                if p["id"] == p_id:
                    p["text"] = p["text"] + "\n" + text_str
                    break

        # Always create child chunk
        child_chunks.append({
            "text": text_str,
            "parent_id": parent_map[key],
            "page": page,
            "heading": heading
        })

    return parent_chunks, child_chunks