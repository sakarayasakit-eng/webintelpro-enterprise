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
        "weaviate.connect_to_",
    )),
    Signature("Milvus", AICategory.VECTOR_DB, patterns=(
        "pymilvus", "milvus-io", "MilvusClient(", "connections.connect(",
    )),
    Signature("Chroma", AICategory.VECTOR_DB, patterns=(
        "chromadb", "from chromadb import", "chromadb.PersistentClient",
        "chroma.Client(",
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
)
