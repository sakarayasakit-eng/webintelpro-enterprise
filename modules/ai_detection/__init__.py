"""
WebIntelPro Enterprise X
AI Stack Detection (Phase 2D)

An additive, opt-in detection capability that identifies a page's AI stack --
hosted providers (OpenAI, Anthropic, Google Gemini, Vertex AI, Azure OpenAI,
Groq, Mistral, Cohere, Together AI, Perplexity, Fireworks AI, OpenRouter,
xAI, DeepSeek, Hugging Face), open-source model references (Llama, Qwen,
Mistral/Mixtral, Gemma, Phi, Falcon, StableLM), local inference runners
(Ollama, llama.cpp, LM Studio, LocalAI), orchestration frameworks (LangChain,
LangGraph, LlamaIndex, Haystack, Semantic Kernel, DSPy, AutoGen, CrewAI,
OpenAI Agents SDK, Mastra, PydanticAI), client SDKs (Vercel AI SDK,
OpenAI/Anthropic/Google AI SDKs, Hugging Face JS, Transformers.js), vector
databases (Pinecone, Weaviate, Milvus, Chroma, Qdrant, Redis Vector,
pgvector, FAISS, LanceDB, Azure AI Search, Supabase Vector), embedding
services (OpenAI, Voyage AI, Cohere, Jina AI, Nomic, BGE, Sentence
Transformers) and AI infrastructure (Replicate, Modal, Baseten, RunPod,
Hugging Face Inference Endpoints) -- from the HTML and JavaScript already
fetched for it, plus response header names.

Public surface
--------------
* :class:`AIStackDetector`     - the orchestrator; returns an
  :class:`AIDetectionAnalysis` carrying both :class:`technology.models.Technology`
  detections and the structured :class:`AIDetectionReport`. This is what
  :class:`technology.detector.TechnologyDetector` calls when
  ``detect(analyze_ai_stack=True)``.
* :class:`AIDetectionConfig`   - every limit and switch for the stage
  (network-free, always).
* :mod:`providers`, :mod:`frameworks`, :mod:`vector_db`, :mod:`embeddings` -
  the per-category signature tables; extending detection normally means
  adding a pattern to one of these.

The sub-system introduces no parallel machinery: it emits the project-wide
``Technology`` model and reuses the existing ``RuleEngine``, ``VersionEngine``
and ``ConfidenceEngine`` for all matching, version extraction and scoring.
"""

from __future__ import annotations

from . import embeddings, frameworks, providers, vector_db
from .detector import AI_EVIDENCE_SOURCE, ALL_SIGNATURES, AIStackDetector
from .models import (
    AICategory,
    AIDetectionAnalysis,
    AIDetectionConfig,
    AIDetectionReport,
    AIFinding,
    DiscoverySource,
    Signature,
)

__all__ = [
    # orchestration
    "AIStackDetector",
    "AIDetectionAnalysis",
    "AIDetectionConfig",
    # signature tables
    "providers",
    "frameworks",
    "vector_db",
    "embeddings",
    "ALL_SIGNATURES",
    # models
    "AIDetectionReport",
    "AIFinding",
    "Signature",
    "AICategory",
    "DiscoverySource",
    # confidence source key
    "AI_EVIDENCE_SOURCE",
]
