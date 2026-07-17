"""
WebIntelPro Enterprise X
AI Stack Detection (Phase 2D) - AI Providers, Open-Source Models, Local AI

Signature tables only -- matching happens once, generically, in
:mod:`detector`. Each :class:`~modules.ai_detection.models.Signature` pairs a
display name with the patterns that identify it in page text (client SDK
imports, API host names, environment-variable names, model-name strings) or
in response header names.

Precision over recall: every pattern here is a multi-character, brand- or
host-specific token (an API host, an env var name, a hyphenated model
identifier) -- never a bare dictionary word -- so a single stray match is
still meaningful evidence, matching the project-wide fingerprinting
convention (see technology/fingerprints/*.py).

Two deliberate additions on top of that baseline, both verified empirically
against the vendors' own live homepages before being added:

* **Bare vendor apex domains** (e.g. ``"anthropic.com"``, ``"groq.com"``).
  Integration-only patterns (API hosts, SDK imports, env-var names) never
  match a vendor's *own* marketing site -- it doesn't call its own API. The
  bare domain reliably does (canonical link, OG tags, JSON-LD, footer),
  mirroring the pre-existing "pinecone.io"/"qdrant.tech" precedent. Skipped
  for domains short/generic enough for substring collisions with unrelated
  sites (e.g. ``"x.ai"`` would match inside "netflix.ai"; ``"cohere.com"``
  is fine, ``"x.ai"`` is not).
* **Durable hyphen-qualified brand prefixes** (e.g. ``"claude-"``,
  ``"mistral-"``, ``"grok-"``, ``"deepseek-"``) instead of only enumerating
  today's model slugs. Exact model-version strings go stale within months
  (e.g. Anthropic's own homepage now advertises "claude-sonnet-5", not the
  older "claude-3-5-sonnet" this file used to match exclusively); a
  hyphenated brand prefix keeps matching future versions without edits.
  Only used where the bare word before the hyphen isn't ordinary English
  (skipped for Cohere's "command-" and Perplexity's "sonar-", both common
  enough words/products elsewhere -- SonarQube, command-line -- to risk
  false positives).
"""

from __future__ import annotations

from typing import Tuple

from .models import AICategory, Signature

# ---------------------------------------------------------------------------
# AI Providers -- hosted, API-key-gated model providers.
# ---------------------------------------------------------------------------
PROVIDERS: Tuple[Signature, ...] = (
    Signature("OpenAI", AICategory.PROVIDER, patterns=(
        "api.openai.com", "openai.com/v1", "openai.com", "OPENAI_API_KEY",
        "from openai import", "require('openai')", "require(\"openai\")",
        "new OpenAI(", "chat.completions.create", "openai/v1/chat/completions",
        "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4.1", "gpt-4.5",
        "gpt-5", "o1-preview", "o1-mini", "o3-mini", "o3-pro", "o4-mini",
        "gpt-image-1",
    ), headers=("openai-organization", "openai-version", "openai-processing-ms")),

    Signature("Anthropic", AICategory.PROVIDER, patterns=(
        "api.anthropic.com", "anthropic.com", "ANTHROPIC_API_KEY",
        "from anthropic import", "new Anthropic(", "anthropic.messages.create",
        "claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku", "claude-3-sonnet",
        "claude-",
    ), headers=("anthropic-version", "anthropic-ratelimit-requests-limit")),

    Signature("Google Gemini", AICategory.PROVIDER, patterns=(
        "generativelanguage.googleapis.com", "GEMINI_API_KEY",
        "GOOGLE_GENERATIVE_AI_API_KEY", "genai.GenerativeModel",
        "gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro-vision", "gemini-2.0",
        "gemini-2.5", "gemini-", "ai.google.dev", "aistudio.google.com",
    )),

    Signature("Vertex AI", AICategory.PROVIDER, patterns=(
        "aiplatform.googleapis.com", "vertexai.generative_models",
        "from vertexai import", "@google-cloud/vertexai", "vertexai.init(",
        "publishers/google/models/gemini", "cloud.google.com/vertex-ai",
    )),

    Signature("Azure OpenAI", AICategory.PROVIDER, patterns=(
        "openai.azure.com", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
        "@azure/openai", "AzureOpenAI(", "cognitiveservices.azure.com/openai",
    )),

    Signature("Groq", AICategory.PROVIDER, patterns=(
        "api.groq.com", "groq.com", "GROQ_API_KEY", "from groq import",
        "new Groq(", "groq.chat.completions",
    )),

    Signature("Mistral AI", AICategory.PROVIDER, patterns=(
        "api.mistral.ai", "mistral.ai", "MISTRAL_API_KEY", "from mistralai import",
        "new MistralClient(", "mistral-large-latest", "mistral-small-latest",
        "mistral-medium", "mistral-nemo", "mistral-",
    )),

    Signature("Cohere", AICategory.PROVIDER, patterns=(
        "api.cohere.ai", "api.cohere.com", "cohere.com", "COHERE_API_KEY",
        "from cohere import", "cohere.Client(", "cohere.ClientV2(",
        "command-r-plus", "command-r", "command-a", "command-light",
        "command-nightly",
    )),

    Signature("Together AI", AICategory.PROVIDER, patterns=(
        "api.together.xyz", "together.ai", "TOGETHER_API_KEY",
        "from together import", "Together().chat", "together.ai/models",
    )),

    Signature("Perplexity", AICategory.PROVIDER, patterns=(
        "api.perplexity.ai", "perplexity.ai", "PERPLEXITY_API_KEY", "pplx-api",
        "sonar-medium-online", "sonar-small-online", "sonar-pro",
        "sonar-reasoning-pro", "sonar-reasoning", "sonar-deep-research",
    )),

    Signature("Fireworks AI", AICategory.PROVIDER, patterns=(
        "fireworks.ai", "api.fireworks.ai", "FIREWORKS_API_KEY",
        "from fireworks import", "fireworks-ai",
    )),

    Signature("OpenRouter", AICategory.PROVIDER, patterns=(
        "openrouter.ai", "api.openrouter.ai", "OPENROUTER_API_KEY",
        "openrouter/auto", "@openrouter/ai-sdk-provider",
    )),

    Signature("xAI", AICategory.PROVIDER, patterns=(
        "api.x.ai", "XAI_API_KEY", "grok-beta", "grok-2", "grok-1.5",
        "grok-3", "grok-4", "grok-code",
    )),

    Signature("DeepSeek", AICategory.PROVIDER, patterns=(
        "api.deepseek.com", "deepseek.com", "DEEPSEEK_API_KEY", "deepseek-chat",
        "deepseek-coder", "deepseek-reasoner", "deepseek-v3", "deepseek-r1",
    )),

    Signature("Hugging Face", AICategory.PROVIDER, patterns=(
        "huggingface.co", "api-inference.huggingface.co", "HUGGINGFACE_API_KEY",
        "HUGGINGFACEHUB_API_TOKEN", "HF_TOKEN", "huggingface_hub",
        "from huggingface_hub import",
    )),
)

# ---------------------------------------------------------------------------
# Open Source Models -- weight/model-family references (any deployment).
# Names are qualified (version/vendor-scoped) to avoid colliding with
# ordinary prose (e.g. bare "phi" or "falcon").
# ---------------------------------------------------------------------------
OPEN_SOURCE_MODELS: Tuple[Signature, ...] = (
    Signature("Llama", AICategory.OPEN_SOURCE_MODEL, patterns=(
        "meta-llama/", "llama-3", "llama-2-7b", "llama-2-13b", "llama-2-70b",
        "llama3.1", "llama3.2", "llama-3.3", "llama-4", "llama3.3",
    )),
    Signature("Qwen", AICategory.OPEN_SOURCE_MODEL, patterns=(
        "qwen/qwen", "qwen2-", "qwen2.5-", "qwen-7b", "qwen-14b", "qwen3-",
    )),
    Signature("Mistral / Mixtral (open weights)", AICategory.OPEN_SOURCE_MODEL, patterns=(
        "mistralai/mistral-7b", "mistralai/mixtral", "mixtral-8x7b",
        "mixtral-8x22b", "open-mixtral", "open-mistral",
    )),
    Signature("Gemma", AICategory.OPEN_SOURCE_MODEL, patterns=(
        "google/gemma", "gemma-2b", "gemma-7b", "gemma-2-9b", "gemma-2-27b",
    )),
    Signature("Phi", AICategory.OPEN_SOURCE_MODEL, patterns=(
        "microsoft/phi", "phi-2", "phi-3-mini", "phi-3-small", "phi-3-medium",
    )),
    Signature("Falcon", AICategory.OPEN_SOURCE_MODEL, patterns=(
        "tiiuae/falcon", "falcon-7b", "falcon-40b", "falcon-180b",
    )),
    Signature("StableLM", AICategory.OPEN_SOURCE_MODEL, patterns=(
        "stabilityai/stablelm", "stablelm-2", "stablelm-zephyr",
    )),
)

# ---------------------------------------------------------------------------
# Local AI -- self-hosted inference runners/servers.
# ---------------------------------------------------------------------------
LOCAL_AI: Tuple[Signature, ...] = (
    Signature("Ollama", AICategory.LOCAL_AI, patterns=(
        "localhost:11434", "127.0.0.1:11434", "from ollama import",
        "ollama.chat(", "ollama.pull(", "ollama.list(",
        "ollama.com", "ollama.ai", "OLLAMA_HOST", "ollama pull", "ollama run",
    )),
    Signature("llama.cpp", AICategory.LOCAL_AI, patterns=(
        "llama.cpp", "llama-cpp-python", "ggml-model-", ".gguf",
    )),
    Signature("LM Studio", AICategory.LOCAL_AI, patterns=(
        "lm-studio", "lmstudio", "localhost:1234/v1",
    )),
    Signature("LocalAI", AICategory.LOCAL_AI, patterns=(
        "go-skynet/localai", "localai.io", "localhost:8080/v1/chat/completions",
    )),
)
