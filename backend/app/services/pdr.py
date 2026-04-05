from typing import List, Dict, Tuple


def build_pdr_structure(
    structured_chunks: List[Dict]
) -> Tuple[List[Dict], List[Dict]]:
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

    parent_map = {}
    parent_chunks = []
    child_chunks = []

    parent_id_counter = 0

    for chunk in structured_chunks:
        page = chunk.get("page")
        heading = chunk.get("heading", "General")
        text = chunk.get("text", "")

        # Unique parent key
        key = f"{page}_{heading}"

        if key not in parent_map:
            parent_id = f"parent_{parent_id_counter}"
            parent_map[key] = parent_id

            parent_chunks.append({
                "id": parent_id,
                "page": page,
                "heading": heading,
                "text": text
            })

            parent_id_counter += 1
        else:
            # Append text to existing parent
            parent_id = parent_map[key]

            for p in parent_chunks:
                if p["id"] == parent_id:
                    p["text"] += "\n" + text
                    break

        # Always create child chunk
        child_chunks.append({
            "text": text,
            "parent_id": parent_map[key],
            "page": page,
            "heading": heading
        })

    return parent_chunks, child_chunks