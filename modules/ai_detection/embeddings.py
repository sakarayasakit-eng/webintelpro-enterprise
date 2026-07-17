"""
WebIntelPro Enterprise X
AI Stack Detection (Phase 2D) - Embedding Services & AI Infrastructure

Signature tables only -- see :mod:`providers` for the shared design notes
(precision-first patterns, generic scanning lives in :mod:`detector`).
"""

from __future__ import annotations

from typing import Tuple

from .models import AICategory, Signature

# ---------------------------------------------------------------------------
# Embedding Services -- text/vector embedding model providers.
# ---------------------------------------------------------------------------
EMBEDDING_SERVICES: Tuple[Signature, ...] = (
    Signature("OpenAI Embeddings", AICategory.EMBEDDING, patterns=(
        "text-embedding-ada-002", "text-embedding-3-small",
        "text-embedding-3-large", "embeddings.create(",
    )),
    Signature("Voyage AI", AICategory.EMBEDDING, patterns=(
        "voyageai", "api.voyageai.com", "voyage-2", "voyage-large-2",
        "VOYAGE_API_KEY",
    )),
    Signature("Cohere Embeddings", AICategory.EMBEDDING, patterns=(
        "embed-english-v3.0", "embed-multilingual-v3.0", "cohere.embed(",
    )),
    Signature("Jina AI", AICategory.EMBEDDING, patterns=(
        "jina-embeddings", "api.jina.ai", "jina-clip-",
    )),
    Signature("Nomic", AICategory.EMBEDDING, patterns=(
        "nomic-embed-text", "nomic-ai/nomic-embed", "nomic.atlas",
    )),
    Signature("BGE", AICategory.EMBEDDING, patterns=(
        "bge-large", "bge-base", "bge-small", "bge-m3", "baai/bge",
    )),
    Signature("Sentence Transformers", AICategory.EMBEDDING, patterns=(
        "sentence-transformers", "sentence_transformers", "SentenceTransformer(",
    )),
)

# ---------------------------------------------------------------------------
# AI Infrastructure -- hosted inference / deployment platforms.
# ---------------------------------------------------------------------------
AI_INFRASTRUCTURE: Tuple[Signature, ...] = (
    Signature("Replicate", AICategory.INFRASTRUCTURE, patterns=(
        "replicate.com", "REPLICATE_API_TOKEN", "from replicate import",
        "replicate.run(",
    )),
    Signature("Modal", AICategory.INFRASTRUCTURE, patterns=(
        "modal.com", "import modal", "@app.function(", "modal.App(",
    )),
    Signature("Baseten", AICategory.INFRASTRUCTURE, patterns=(
        "baseten.co", "truss_config.yaml", "baseten.deploy(",
    )),
    Signature("RunPod", AICategory.INFRASTRUCTURE, patterns=(
        "runpod.io", "RUNPOD_API_KEY", "runpod.serverless",
    )),
    Signature("Hugging Face Inference Endpoints", AICategory.INFRASTRUCTURE, patterns=(
        "endpoints.huggingface.cloud", "huggingface.co/inference-endpoints",
        "hf_inference_endpoint",
    )),
)
