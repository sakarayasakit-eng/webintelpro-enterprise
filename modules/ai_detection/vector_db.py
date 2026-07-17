"""
WebIntelPro Enterprise X
AI Stack Detection (Phase 2D) - Vector Databases

Signature tables only -- see :mod:`providers` for the shared design notes
(precision-first patterns, generic scanning lives in :mod:`detector`).
"""

from __future__ import annotations

from typing import Tuple

from .models import AICategory, Signature

VECTOR_DATABASES: Tuple[Signature, ...] = (
    Signature("Pinecone", AICategory.VECTOR_DB, patterns=(
        "pinecone.io", "@pinecone-database/pinecone", "from pinecone import",
        "pinecone.Index(", "PINECONE_API_KEY",
    )),
    Signature("Weaviate", AICategory.VECTOR_DB, patterns=(
        "weaviate-client", "weaviate-ts-client", "weaviate.Client(",
        "weaviate.connect_to_", "weaviate.io",
    )),
    Signature("Milvus", AICategory.VECTOR_DB, patterns=(
        "pymilvus", "milvus-io", "MilvusClient(", "connections.connect(",
        "milvus.io",
    )),
    Signature("Chroma", AICategory.VECTOR_DB, patterns=(
        "chromadb", "from chromadb import", "chromadb.PersistentClient",
        "chroma.Client(", "trychroma.com",
    )),
    Signature("Qdrant", AICategory.VECTOR_DB, patterns=(
        "qdrant-client", "@qdrant/js-client-rest", "QdrantClient(",
        "qdrant.tech",
    )),
    Signature("Redis Vector", AICategory.VECTOR_DB, patterns=(
        "redis-vl", "redisvl", "FT.CREATE", "redisearch",
    )),
    Signature("pgvector", AICategory.VECTOR_DB, patterns=(
        "pgvector", "create extension vector", "vector(1536)",
        "vector_cosine_ops",
    )),
    Signature("FAISS", AICategory.VECTOR_DB, patterns=(
        "faiss-cpu", "faiss-gpu", "import faiss", "IndexFlatL2(", "IndexIVFFlat(",
    )),
    Signature("LanceDB", AICategory.VECTOR_DB, patterns=(
        "lancedb", "@lancedb/lancedb", "lancedb.connect(",
    )),
    Signature("Azure AI Search", AICategory.VECTOR_DB, patterns=(
        "search.windows.net", "azure-search-documents", "AzureSearch(",
        "@azure/search-documents",
    )),
    # Deliberately NOT keyed on the bare "supabase.com" domain -- Supabase is
    # a general-purpose backend used by countless non-AI apps; tagging every
    # one of them as "AI stack" would be a precision regression. Keyed only
    # on phrasing/imports specific to its vector feature (verified present on
    # supabase.com's own marketing copy).
    Signature("Supabase Vector", AICategory.VECTOR_DB, patterns=(
        "supabase vector", "supabase.com/docs/guides/ai", "@supabase/vecs",
        "vecs.create_client(", "supabase.com/vector",
    )),
)
