# backend/storage package
from backend.storage.elasticsearch_client import (
    ElasticsearchClient,
    get_elasticsearch_client,
    reset_elasticsearch_client,
    ESIndex,
    InMemoryESStore,
)
from backend.storage.chromadb_client import (
    ChromaDBClient,
    get_chromadb_client,
    reset_chromadb_client,
    COLLECTION_DOCUMENT_CHUNKS,
    COLLECTION_KNOWLEDGE_BASE,
    COLLECTION_TICKET_PRECEDENTS,
)

