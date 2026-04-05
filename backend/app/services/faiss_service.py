import faiss
import numpy as np
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.core.config import settings
from datetime import datetime
from collections import defaultdict


logger = logging.getLogger(__name__)

class FAISSManager:
    def __init__(self):
        self.index = None
        # parents: map of filename -> List[str]
        self.metadata = {"documents": [], "parents": {}, "version": 1}
        self.index_path = Path(settings.INDEX_PATH) / "documents.index"
        self.metadata_path = Path(settings.INDEX_PATH) / "metadata.json"
        self.dimension = settings.EMBEDDING_DIM
        self.init_index()
    
    def init_index(self):
        """Initialize or load FAISS index."""
        try:
            if self.index_path.exists() and self.metadata_path.exists():
                logger.info("Loading existing FAISS index...")
                self.index = faiss.read_index(str(self.index_path))
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)
                
                # Ensure 'parents' exists in loaded metadata
                if 'parents' not in self.metadata:
                    self.metadata['parents'] = {}
                    
                logger.info(f"✅ Loaded index with {len(self.metadata['documents'])} documents")
            else:
                logger.info("Creating new FAISS index...")
                self.index = faiss.IndexFlatL2(self.dimension)
                self.metadata = {"documents": [], "parents": {}, "version": 1}
        except Exception as e:
            logger.error(f"Error initializing index: {e}")
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = {"documents": [], "parents": {}, "version": 1}
    
    def add_vectors(
        self, 
        embeddings: List[List[float]], 
        documents: List[str], 
        metadata: List[Dict[str, Any]],
        parent_chunks: Optional[List[str]] = None
    ) -> int:
        """Add vectors and documents to FAISS index."""
        if not embeddings:
            return len(self.metadata['documents'])
        
        # Convert to numpy array
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        # Add to index
        self.index.add(embeddings_array)
        
        # Determine source name from metadata if possible
        source_name = metadata[0].get("filename", "unknown") if metadata else "unknown"
        
        # Handle parent chunks storage
        if parent_chunks:
            self.metadata['parents'][source_name] = parent_chunks

        # Track metadata for chunks
        for i, doc in enumerate(documents):
            meta = metadata[i] if i < len(metadata) else {}
            self.metadata['documents'].append({
                "id": len(self.metadata['documents']),
                "text": f"{meta.get('heading', '')}\n{doc}",
                "source": meta.get("filename", source_name),
                "parent_id": meta.get("parent_id"),
                "page": meta.get("page"),
                "heading": meta.get("heading"),
                "timestamp": datetime.now().isoformat()
            })
        
        # Persist
        self._save()
        logger.info(f"✅ Added {len(embeddings)} vectors to index")
        
        return len(self.metadata['documents'])

    def get_parent_text(self, source: str, parent_id: Any) -> Optional[str]:
        """Retrieve the larger parent text for a given source and id."""
        if parent_id is None:
            return None
        try:
            parents = self.metadata['parents'].get(source, [])
            logger.info(f"🔍 Fetching parent '{parent_id}' for source '{source}' (found {len(parents)} parents)")
            if not parents:
                return None
            
            if isinstance(parents[0], dict):
                # New structured format: parents is a list of dicts
                for p in parents:
                    if p.get("id") == parent_id:
                        logger.info(f"✅ Found parent heading: {p.get('heading')}")
                        return p.get("text")
                logger.warning(f"❌ Parent ID {parent_id} not found in structured metadata")
                return None
            else:
                # Old format: parents is a list of strings and parent_id is an int
                idx = int(parent_id)
                logger.info(f"✅ Found parent index: {idx}")
                return parents[idx]
        except Exception as e:
            logger.error(f"❌ Error in get_parent_text: {e}")
            return None
    
    def search(self, query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """Search FAISS index."""
        if not self.index or self.index.ntotal == 0:
            return []
        
        try:
            query_array = np.array([query_embedding], dtype=np.float32)
            distances, indices = self.index.search(query_array, min(k, self.index.ntotal))
            
            logger.info(f"🎯 FAISS search raw indices: {indices[0]}")
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx < len(self.metadata['documents']):
                    similarity = float(1 / (1 + distances[0][i]))
                    doc = self.metadata['documents'][int(idx)]
                    logger.info(f"🏆 Rank {i+1}: Score {similarity:.4f} | Source: {doc['source']}")
                    results.append({
                        "id": int(idx),
                        "distance": float(distances[0][i]),
                        "similarity": similarity,
                        "document": doc
                    })
            
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        sources = list(set(d['source'] for d in self.metadata['documents']))
        return {
            "indexed": len(self.metadata['documents']),
            "sources": sources,
            "stats": {
                "totalChunks": len(self.metadata['documents']),
                "totalParents": sum(len(p) for p in self.metadata['parents'].values()),
                "uniqueSources": len(sources),
                "indexDimension": self.dimension,
                "model": settings.EMBEDDING_MODEL
            }
        }
    
    def clear(self) -> bool:
        """Clear index."""
        try:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = {"documents": [], "parents": {}, "version": 1}
            
            if self.index_path.exists():
                self.index_path.unlink()
            if self.metadata_path.exists():
                self.metadata_path.unlink()
            
            logger.info("✅ Index cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing index: {e}")
            return False
    
    def _save(self):
        """Persist index to disk."""
        try:
            faiss.write_index(self.index, str(self.index_path))
            with open(self.metadata_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving index: {e}")

    def _group_by_parent(self, results):
        parent_scores = defaultdict(float)
        parent_docs = {}

        for r in results:
            doc = r["document"]
            pid = doc.get("parent_id")

            if not pid:
                continue

            parent_scores[pid] += r["similarity"]
            parent_docs[pid] = doc

        return parent_scores, parent_docs


    def _rank_parents(self, parent_scores):
        return sorted(parent_scores.items(), key=lambda x: x[1], reverse=True)


    def build_context(self, results, max_parents: int = 3) -> str:
        """
        Build final LLM context using Parent Document Retrieval.
        """

        parent_scores, parent_docs = self._group_by_parent(results)
        ranked_parents = self._rank_parents(parent_scores)

        context_blocks = []

        for parent_id, score in ranked_parents[:max_parents]:
            doc = parent_docs[parent_id]
            source = doc["source"]

            parent_text = self.get_parent_text(source, parent_id)

            if not parent_text:
                continue

            context_blocks.append(
                f"[Source: {source} | Page: {doc.get('page')} | Section: {doc.get('heading')}]\n"
                f"{parent_text}"
            )

        final_context = "\n\n---\n\n".join(context_blocks)

        logger.info(f"🧠 Built context with {len(context_blocks)} parent sections")

        return final_context
        
# Global instance
faiss_manager = FAISSManager()
