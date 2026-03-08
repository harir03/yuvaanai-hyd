"""
Intelli-Credit — ChromaDB Vector Store Client

Provides semantic vector search over document chunks for RAG retrieval,
knowledge base entries, and resolved ticket precedent lookup.

Falls back to in-memory numpy-based vector search when ChromaDB is unavailable
— critical for hackathon demo without Docker.

Usage:
    client = get_chromadb_client()
    await client.initialize()
    await client.add_documents("session_123", chunks, metadatas)
    results = await client.search("What is the DSCR ratio?", top_k=5)
"""

import logging
import uuid
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

from backend.ml.embeddings import embed_texts, embed_single, cosine_similarity, EMBEDDING_DIM

logger = logging.getLogger(__name__)

# ── Collection names ──
COLLECTION_DOCUMENT_CHUNKS = "document_chunks"
COLLECTION_KNOWLEDGE_BASE = "knowledge_base"
COLLECTION_TICKET_PRECEDENTS = "ticket_precedents"


class InMemoryVectorStore:
    """In-memory vector store mimicking ChromaDB for offline/demo usage.

    Stores embeddings as numpy arrays and performs brute-force cosine search.
    """

    def __init__(self):
        # collection_name → { ids: [], embeddings: np.ndarray, documents: [], metadatas: [] }
        self._collections: Dict[str, Dict[str, Any]] = {}

    def _ensure_collection(self, name: str) -> Dict[str, Any]:
        if name not in self._collections:
            self._collections[name] = {
                "ids": [],
                "embeddings": np.zeros((0, EMBEDDING_DIM), dtype=np.float32),
                "documents": [],
                "metadatas": [],
            }
        return self._collections[name]

    def add(
        self,
        collection: str,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: Optional[np.ndarray] = None,
    ) -> None:
        """Add documents to a collection."""
        coll = self._ensure_collection(collection)

        if embeddings is None:
            embeddings = embed_texts(documents)

        coll["ids"].extend(ids)
        coll["documents"].extend(documents)
        coll["metadatas"].extend(metadatas)
        if coll["embeddings"].shape[0] == 0:
            coll["embeddings"] = embeddings
        else:
            coll["embeddings"] = np.vstack([coll["embeddings"], embeddings])

    def query(
        self,
        collection: str,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search a collection by semantic similarity."""
        coll = self._collections.get(collection)
        if coll is None or len(coll["ids"]) == 0:
            return []

        query_vec = embed_single(query_text)

        # Compute similarities
        scores: List[Tuple[int, float]] = []
        for i in range(len(coll["ids"])):
            # Apply metadata filter if provided
            if where:
                meta = coll["metadatas"][i]
                match = all(meta.get(k) == v for k, v in where.items())
                if not match:
                    continue
            sim = cosine_similarity(query_vec, coll["embeddings"][i])
            scores.append((i, float(sim)))

        # Sort by similarity descending
        scores.sort(key=lambda x: x[1], reverse=True)
        top = scores[:top_k]

        results = []
        for idx, score in top:
            results.append({
                "id": coll["ids"][idx],
                "document": coll["documents"][idx],
                "metadata": coll["metadatas"][idx],
                "score": score,
            })
        return results

    def delete_collection(self, collection: str) -> None:
        """Delete an entire collection."""
        self._collections.pop(collection, None)

    def count(self, collection: str) -> int:
        """Count documents in a collection."""
        coll = self._collections.get(collection)
        return len(coll["ids"]) if coll else 0

    def list_collections(self) -> List[str]:
        """List all collection names."""
        return list(self._collections.keys())


class ChromaDBClient:
    """Async ChromaDB client with in-memory fallback.

    Tries to connect to a real ChromaDB server on initialize().
    Falls back to InMemoryVectorStore if unavailable.
    """

    def __init__(self, host: str = "localhost", port: int = 8100):
        self._host = host
        self._port = port
        self._client: Any = None
        self._memory = InMemoryVectorStore()
        self._use_chroma = False
        self.is_initialized = False

    @property
    def backend(self) -> str:
        return "chromadb" if self._use_chroma else "memory"

    async def initialize(self) -> None:
        """Initialize the ChromaDB connection. Falls back to in-memory."""
        try:
            import chromadb
            self._client = chromadb.HttpClient(host=self._host, port=self._port)
            # Test connectivity
            self._client.heartbeat()
            self._use_chroma = True
            logger.info(f"[ChromaDB] Connected to {self._host}:{self._port}")
        except ImportError:
            self._use_chroma = False
            logger.warning("[ChromaDB] chromadb not installed — using in-memory vector store")
        except Exception as e:
            self._use_chroma = False
            logger.warning(f"[ChromaDB] Connection failed ({e}) — using in-memory vector store")
        self.is_initialized = True

    async def close(self) -> None:
        """Close the ChromaDB connection."""
        self._client = None
        self._use_chroma = False
        logger.info("[ChromaDB] Connection closed")

    # ── Core operations ──

    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> int:
        """Add document chunks to a collection.

        Args:
            collection_name: Target collection.
            documents: List of text chunks.
            metadatas: Optional metadata for each chunk.
            ids: Optional IDs (auto-generated if not provided).

        Returns:
            Number of documents added.
        """
        if not documents:
            return 0

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        if metadatas is None:
            metadatas = [{} for _ in documents]

        # Generate embeddings
        embeddings = embed_texts(documents)

        if self._use_chroma and self._client is not None:
            try:
                collection = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings.tolist(),
                )
                logger.info(f"[ChromaDB] Added {len(documents)} docs to '{collection_name}'")
                return len(documents)
            except Exception as e:
                logger.warning(f"[ChromaDB] Add failed ({e}), falling back to memory")

        # Fallback to in-memory
        self._memory.add(collection_name, ids, documents, metadatas, embeddings)
        logger.info(f"[ChromaDB/Memory] Added {len(documents)} docs to '{collection_name}'")
        return len(documents)

    async def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search over a collection.

        Args:
            collection_name: Collection to search.
            query: Natural language query.
            top_k: Number of results to return.
            where: Optional metadata filter.

        Returns:
            List of results with id, document, metadata, score.
        """
        if self._use_chroma and self._client is not None:
            try:
                collection = self._client.get_collection(name=collection_name)
                query_embedding = embed_single(query).tolist()
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    where=where,
                )
                output = []
                for i in range(len(results["ids"][0])):
                    output.append({
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "score": 1.0 - (results["distances"][0][i] if results["distances"] else 0),
                    })
                return output
            except Exception as e:
                logger.warning(f"[ChromaDB] Search failed ({e}), falling back to memory")

        return self._memory.query(collection_name, query, top_k, where)

    async def add_ticket_precedent(
        self,
        ticket_id: str,
        description: str,
        resolution: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a resolved ticket as a precedent for future lookup."""
        doc = f"Issue: {description}\nResolution: {resolution}"
        meta = metadata or {}
        meta["ticket_id"] = ticket_id
        meta["type"] = "ticket_precedent"
        await self.add_documents(
            COLLECTION_TICKET_PRECEDENTS,
            documents=[doc],
            metadatas=[meta],
            ids=[f"ticket_{ticket_id}"],
        )

    async def find_similar_tickets(
        self,
        description: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find similar past tickets by vector similarity."""
        return await self.search(
            COLLECTION_TICKET_PRECEDENTS,
            query=description,
            top_k=top_k,
        )

    async def add_knowledge_entry(
        self,
        entry_id: str,
        content: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a knowledge base entry (e.g., sector benchmarks, RBI circulars)."""
        meta = metadata or {}
        meta["source"] = source
        meta["type"] = "knowledge_base"
        await self.add_documents(
            COLLECTION_KNOWLEDGE_BASE,
            documents=[content],
            metadatas=[meta],
            ids=[entry_id],
        )

    async def rag_retrieve(
        self,
        session_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """RAG retrieval — search document chunks for a specific session."""
        return await self.search(
            COLLECTION_DOCUMENT_CHUNKS,
            query=query,
            top_k=top_k,
            where={"session_id": session_id},
        )

    def count(self, collection_name: str) -> int:
        """Count documents in a collection."""
        if self._use_chroma and self._client is not None:
            try:
                collection = self._client.get_collection(name=collection_name)
                return collection.count()
            except Exception:
                pass
        return self._memory.count(collection_name)


# ── Singleton ──
_instance: Optional[ChromaDBClient] = None


def get_chromadb_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> ChromaDBClient:
    """Get or create the singleton ChromaDB client."""
    global _instance
    if _instance is None:
        _instance = ChromaDBClient(
            host=host or "localhost",
            port=port or 8100,
        )
    return _instance


def reset_chromadb_client() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    _instance = None
