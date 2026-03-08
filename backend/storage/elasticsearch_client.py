"""
Intelli-Credit — Elasticsearch Client

Async Elasticsearch client for 4 indices:
- document_store: Extracted text chunks + metadata (doc type, page, confidence)
- research_intelligence: Web research results + source tier
- company_profiles: Past assessments, peer data, sector benchmarks
- regulatory_watchlist: RBI circulars, SEBI regs, MCA notifications, GST council

Falls back to in-memory lists when Elasticsearch is unavailable — critical for
hackathon demo without Docker.

Usage:
    es = get_elasticsearch_client()
    await es.initialize()
    await es.index_document("document_store", {"content": "...", "doc_type": "annual_report"})
    results = await es.search("document_store", "revenue growth steel sector")
    await es.index_regulatory_item({...})
"""

import logging
import time
import uuid
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Index Names
# ──────────────────────────────────────────────

class ESIndex(str, Enum):
    DOCUMENT_STORE = "document_store"
    RESEARCH_INTELLIGENCE = "research_intelligence"
    COMPANY_PROFILES = "company_profiles"
    REGULATORY_WATCHLIST = "regulatory_watchlist"


# ──────────────────────────────────────────────
# Index Configuration — Mapping + Settings
# ──────────────────────────────────────────────

INDEX_MAPPINGS: Dict[str, Dict[str, Any]] = {
    ESIndex.DOCUMENT_STORE: {
        "mappings": {
            "properties": {
                "session_id": {"type": "keyword"},
                "doc_type": {"type": "keyword"},
                "page": {"type": "integer"},
                "content": {"type": "text", "analyzer": "standard"},
                "confidence": {"type": "float"},
                "worker_id": {"type": "keyword"},
                "extracted_entities": {"type": "keyword"},
                "created_at": {"type": "date"},
            }
        }
    },
    ESIndex.RESEARCH_INTELLIGENCE: {
        "mappings": {
            "properties": {
                "session_id": {"type": "keyword"},
                "source": {"type": "keyword"},
                "source_tier": {"type": "integer"},
                "source_weight": {"type": "float"},
                "title": {"type": "text"},
                "content": {"type": "text", "analyzer": "standard"},
                "url": {"type": "keyword"},
                "category": {"type": "keyword"},
                "relevance_score": {"type": "float"},
                "verified": {"type": "boolean"},
                "published_date": {"type": "date"},
                "created_at": {"type": "date"},
            }
        }
    },
    ESIndex.COMPANY_PROFILES: {
        "mappings": {
            "properties": {
                "company_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "cin": {"type": "keyword"},
                "sector": {"type": "keyword"},
                "last_assessment_score": {"type": "integer"},
                "last_assessment_band": {"type": "keyword"},
                "last_assessment_outcome": {"type": "keyword"},
                "assessment_count": {"type": "integer"},
                "peer_comparison": {"type": "object"},
                "sector_benchmarks": {"type": "object"},
                "updated_at": {"type": "date"},
            }
        }
    },
    ESIndex.REGULATORY_WATCHLIST: {
        "mappings": {
            "properties": {
                "source": {"type": "keyword"},
                "regulation_type": {"type": "keyword"},
                "title": {"type": "text"},
                "content": {"type": "text", "analyzer": "standard"},
                "url": {"type": "keyword"},
                "sectors_affected": {"type": "keyword"},
                "severity": {"type": "keyword"},
                "effective_date": {"type": "date"},
                "published_date": {"type": "date"},
                "created_at": {"type": "date"},
            }
        }
    },
}


# ──────────────────────────────────────────────
# In-Memory Fallback Store
# ──────────────────────────────────────────────

class InMemoryESStore:
    """
    In-memory Elasticsearch fallback for dev/demo/testing.
    Stores documents as dicts in lists per index.
    Supports basic text search (substring matching).
    """

    def __init__(self):
        self._indices: Dict[str, List[Dict[str, Any]]] = {}

    async def create_index(self, index: str, body: Optional[Dict] = None) -> bool:
        if index not in self._indices:
            self._indices[index] = []
            logger.info(f"[ES-InMemory] Created index: {index}")
        return True

    async def index_exists(self, index: str) -> bool:
        return index in self._indices

    async def index_document(
        self, index: str, document: Dict[str, Any], doc_id: Optional[str] = None,
    ) -> str:
        if index not in self._indices:
            self._indices[index] = []

        doc_id = doc_id or str(uuid.uuid4())
        doc = {"_id": doc_id, **document}
        self._indices[index].append(doc)
        return doc_id

    async def bulk_index(
        self, index: str, documents: List[Dict[str, Any]],
    ) -> int:
        """Index multiple documents at once. Returns count indexed."""
        count = 0
        for doc in documents:
            await self.index_document(index, doc)
            count += 1
        return count

    async def search(
        self,
        index: str,
        query: str,
        size: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Basic text search across text fields with optional keyword filters."""
        if index not in self._indices:
            return []

        results = []
        query_lower = query.lower()

        for doc in self._indices[index]:
            # Check filters first
            if filters:
                match = True
                for key, value in filters.items():
                    if isinstance(value, list):
                        if doc.get(key) not in value:
                            match = False
                            break
                    elif doc.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            # Text search across string fields
            matched = False
            for field, val in doc.items():
                if field == "_id":
                    continue
                if isinstance(val, str) and query_lower in val.lower():
                    matched = True
                    break

            if matched:
                results.append(doc)
                if len(results) >= size:
                    break

        return results

    async def get_document(self, index: str, doc_id: str) -> Optional[Dict[str, Any]]:
        if index not in self._indices:
            return None
        for doc in self._indices[index]:
            if doc.get("_id") == doc_id:
                return doc
        return None

    async def delete_document(self, index: str, doc_id: str) -> bool:
        if index not in self._indices:
            return False
        for i, doc in enumerate(self._indices[index]):
            if doc.get("_id") == doc_id:
                self._indices[index].pop(i)
                return True
        return False

    async def count(self, index: str) -> int:
        return len(self._indices.get(index, []))

    async def delete_index(self, index: str) -> bool:
        if index in self._indices:
            del self._indices[index]
            return True
        return False

    async def close(self):
        pass


# ──────────────────────────────────────────────
# Elasticsearch Client
# ──────────────────────────────────────────────

class ElasticsearchClient:
    """
    Async Elasticsearch client with in-memory fallback.
    Manages all 4 indices for Intelli-Credit.
    """

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        api_key: Optional[str] = None,
    ):
        self._hosts = hosts
        self._api_key = api_key
        self._es = None
        self._store: Optional[InMemoryESStore] = None
        self._use_es = False
        self._initialized = False

    async def initialize(self):
        """Connect to Elasticsearch or fall back to in-memory."""
        if self._initialized:
            return

        if self._hosts:
            try:
                from elasticsearch import AsyncElasticsearch
                self._es = AsyncElasticsearch(
                    hosts=self._hosts,
                    api_key=self._api_key,
                    request_timeout=10,
                )
                info = await self._es.info()
                self._use_es = True
                logger.info(f"[ES] Connected to Elasticsearch {info['version']['number']}")
            except Exception as e:
                logger.warning(f"[ES] Unavailable ({e}), using in-memory fallback")
                self._es = None
                self._store = InMemoryESStore()
                self._use_es = False
        else:
            logger.info("[ES] No hosts configured, using in-memory fallback")
            self._store = InMemoryESStore()
            self._use_es = False

        self._initialized = True

        # Ensure all 4 indices exist
        await self._ensure_indices()

    async def _ensure_initialized(self):
        if not self._initialized:
            await self.initialize()

    async def _ensure_indices(self):
        """Create all 4 indices if they don't exist."""
        for index_name in ESIndex:
            mapping = INDEX_MAPPINGS.get(index_name, {})
            if self._use_es:
                try:
                    exists = await self._es.indices.exists(index=index_name.value)
                    if not exists:
                        await self._es.indices.create(
                            index=index_name.value, body=mapping,
                        )
                        logger.info(f"[ES] Created index: {index_name.value}")
                except Exception as e:
                    logger.warning(f"[ES] Failed to create index {index_name.value}: {e}")
            else:
                await self._store.create_index(index_name.value)

    # ──────────────────────────────────────────────
    # CRUD Operations
    # ──────────────────────────────────────────────

    async def index_document(
        self,
        index: str,
        document: Dict[str, Any],
        doc_id: Optional[str] = None,
    ) -> str:
        """Index a single document. Returns the document ID."""
        await self._ensure_initialized()

        if self._use_es:
            result = await self._es.index(
                index=index, id=doc_id, document=document,
            )
            return result["_id"]
        else:
            return await self._store.index_document(index, document, doc_id)

    async def bulk_index(
        self,
        index: str,
        documents: List[Dict[str, Any]],
    ) -> int:
        """Index multiple documents. Returns count indexed."""
        await self._ensure_initialized()

        if self._use_es:
            from elasticsearch.helpers import async_bulk
            actions = [
                {"_index": index, "_source": doc} for doc in documents
            ]
            success, _ = await async_bulk(self._es, actions)
            return success
        else:
            return await self._store.bulk_index(index, documents)

    async def search(
        self,
        index: str,
        query: str,
        size: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Full-text search across an index.

        Args:
            index: Index name (use ESIndex enum values).
            query: Search query string.
            size: Max results to return.
            filters: Optional keyword field filters.
        """
        await self._ensure_initialized()

        if self._use_es:
            body: Dict[str, Any] = {
                "query": {
                    "bool": {
                        "must": [{"multi_match": {"query": query, "fields": ["*"]}}],
                    }
                },
                "size": size,
            }
            if filters:
                body["query"]["bool"]["filter"] = [
                    {"term": {k: v}} for k, v in filters.items()
                ]
            result = await self._es.search(index=index, body=body)
            return [hit["_source"] for hit in result["hits"]["hits"]]
        else:
            return await self._store.search(index, query, size, filters)

    async def get_document(self, index: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        await self._ensure_initialized()

        if self._use_es:
            try:
                result = await self._es.get(index=index, id=doc_id)
                return result["_source"]
            except Exception:
                return None
        else:
            return await self._store.get_document(index, doc_id)

    async def delete_document(self, index: str, doc_id: str) -> bool:
        """Delete a document by ID."""
        await self._ensure_initialized()

        if self._use_es:
            try:
                await self._es.delete(index=index, id=doc_id)
                return True
            except Exception:
                return False
        else:
            return await self._store.delete_document(index, doc_id)

    async def count(self, index: str) -> int:
        """Count documents in an index."""
        await self._ensure_initialized()

        if self._use_es:
            result = await self._es.count(index=index)
            return result["count"]
        else:
            return await self._store.count(index)

    # ──────────────────────────────────────────────
    # Domain-Specific Operations
    # ──────────────────────────────────────────────

    async def index_document_chunk(
        self,
        session_id: str,
        doc_type: str,
        page: int,
        content: str,
        confidence: float = 1.0,
        worker_id: Optional[str] = None,
        entities: Optional[List[str]] = None,
    ) -> str:
        """Index an extracted document chunk into document_store."""
        return await self.index_document(
            ESIndex.DOCUMENT_STORE.value,
            {
                "session_id": session_id,
                "doc_type": doc_type,
                "page": page,
                "content": content,
                "confidence": confidence,
                "worker_id": worker_id or "",
                "extracted_entities": entities or [],
            },
        )

    async def index_research_finding(
        self,
        session_id: str,
        source: str,
        source_tier: int,
        source_weight: float,
        title: str,
        content: str,
        category: str,
        url: Optional[str] = None,
        verified: bool = False,
        relevance_score: float = 0.0,
    ) -> str:
        """Index a research finding into research_intelligence."""
        return await self.index_document(
            ESIndex.RESEARCH_INTELLIGENCE.value,
            {
                "session_id": session_id,
                "source": source,
                "source_tier": source_tier,
                "source_weight": source_weight,
                "title": title,
                "content": content,
                "category": category,
                "url": url or "",
                "verified": verified,
                "relevance_score": relevance_score,
            },
        )

    async def index_regulatory_item(
        self,
        source: str,
        regulation_type: str,
        title: str,
        content: str,
        url: str = "",
        sectors_affected: Optional[List[str]] = None,
        severity: str = "INFO",
        effective_date: Optional[str] = None,
    ) -> str:
        """Index a regulatory notification into regulatory_watchlist."""
        return await self.index_document(
            ESIndex.REGULATORY_WATCHLIST.value,
            {
                "source": source,
                "regulation_type": regulation_type,
                "title": title,
                "content": content,
                "url": url,
                "sectors_affected": sectors_affected or [],
                "severity": severity,
                "effective_date": effective_date,
            },
        )

    async def search_regulatory(
        self,
        query: str,
        sector: Optional[str] = None,
        size: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search regulatory watchlist with optional sector filter."""
        filters = {"sectors_affected": sector} if sector else None
        return await self.search(
            ESIndex.REGULATORY_WATCHLIST.value, query, size, filters,
        )

    async def index_company_profile(
        self,
        company_name: str,
        cin: Optional[str] = None,
        sector: Optional[str] = None,
        last_score: Optional[int] = None,
        last_band: Optional[str] = None,
        last_outcome: Optional[str] = None,
        assessment_count: int = 0,
    ) -> str:
        """Index or update a company profile."""
        return await self.index_document(
            ESIndex.COMPANY_PROFILES.value,
            {
                "company_name": company_name,
                "cin": cin or "",
                "sector": sector or "",
                "last_assessment_score": last_score,
                "last_assessment_band": last_band,
                "last_assessment_outcome": last_outcome,
                "assessment_count": assessment_count,
            },
        )

    async def get_stats(self) -> Dict[str, Any]:
        """Get document counts per index."""
        await self._ensure_initialized()
        stats = {}
        for index_name in ESIndex:
            stats[index_name.value] = await self.count(index_name.value)
        return stats

    async def close(self):
        """Close the Elasticsearch client."""
        if self._use_es and self._es:
            await self._es.close()
        elif self._store:
            await self._store.close()


# ──────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────

_es_client: Optional[ElasticsearchClient] = None


def get_elasticsearch_client(
    hosts: Optional[List[str]] = None,
    api_key: Optional[str] = None,
) -> ElasticsearchClient:
    """Get or create the singleton ElasticsearchClient."""
    global _es_client
    if _es_client is None:
        _es_client = ElasticsearchClient(hosts, api_key)
    return _es_client


def reset_elasticsearch_client():
    """Reset the singleton (for testing)."""
    global _es_client
    _es_client = None
