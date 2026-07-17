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
"""

from __future__ import annotations

from typing import Tuple

from .models import AICategory, Signature

# ---------------------------------------------------------------------------
# AI Providers -- hosted, API-key-gated model providers.
# ---------------------------------------------------------------------------
PROVIDERS: Tuple[Signature, ...] = (
    Signature("OpenAI", AICategory.PROVIDER, patterns=(
        "api.openai.com", "openai.com/v1", "OPENAI_API_KEY",
        "from openai import", "require('openai')", "require(\"openai\")",
        "new OpenAI(", "chat.completions.create", "openai/v1/chat/completions",
        "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo",
    ), headers=("openai-organization", "openai-version", "openai-processing-ms")),

    Signature("Anthropic", AICategory.PROVIDER, patterns=(
        "api.anthropic.com", "ANTHROPIC_API_KEY", "from anthropic import",
        "new Anthropic(", "anthropic.messages.create", "claude-3-5-sonnet",
        "claude-3-opus", "claude-3-haiku", "claude-3-sonnet",
    ), headers=("anthropic-version", "anthropic-ratelimit-requests-limit")),

    Signature("Google Gemini", AICategory.PROVIDER, patterns=(
        "generativelanguage.googleapis.com", "GEMINI_API_KEY",
        "GOOGLE_GENERATIVE_AI_API_KEY", "genai.GenerativeModel",
        "gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro-vision", "gemini-2.0",
    )),

    Signature("Groq", AICategory.PROVIDER, patterns=(
        "api.groq.com", "GROQ_API_KEY", "from groq import", "new Groq(",
        "groq.chat.completions",
    )),

    Signature("Mistral AI", AICategory.PROVIDER, patterns=(
        "api.mistral.ai", "MISTRAL_API_KEY", "from mistralai import",
        "new MistralClient(", "mistral-large-latest", "mistral-small-latest",
    )),

    Signature("Cohere", AICategory.PROVIDER, patterns=(
        "api.cohere.ai", "api.cohere.com", "COHERE_API_KEY",
        "from cohere import", "cohere.Client(", "cohere.ClientV2(",
        "command-r-plus",
    )),

    Signature("Together AI", AICategory.PROVIDER, patterns=(
        "api.together.xyz", "TOGETHER_API_KEY", "from together import",
        "Together().chat", "together.ai/models",
    )),

    Signature("Perplexity", AICategory.PROVIDER, patterns=(
        "api.perplexity.ai", "PERPLEXITY_API_KEY", "pplx-api",
        "sonar-medium-online", "sonar-small-online",
    )),

    Signature("xAI", AICategory.PROVIDER, patterns=(
        "api.x.ai", "XAI_API_KEY", "grok-beta", "grok-2", "grok-1.5",
    )),

    Signature("DeepSeek", AICategory.PROVIDER, patterns=(
        "api.deepseek.com", "DEEPSEEK_API_KEY", "deepseek-chat",
        "deepseek-coder", "deepseek-reasoner",
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
        "llama3.1", "llama3.2",
    )),
    Signature("Qwen", AICategory.OPEN_SOURCE_MODEL, patterns=(
        "qwen/qwen", "qwen2-", "qwen2.5-", "qwen-7b", "qwen-14b",
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
