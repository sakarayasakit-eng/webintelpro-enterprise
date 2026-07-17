"""
WebIntelPro Enterprise X
AI Stack Detection (Phase 2D) - AI Frameworks & AI SDKs

Signature tables only -- see :mod:`providers` for the shared design notes
(precision-first patterns, generic scanning lives in :mod:`detector`).
"""

from __future__ import annotations

from typing import Tuple

from .models import AICategory, Signature

# ---------------------------------------------------------------------------
# AI Frameworks -- orchestration/agent frameworks built on top of model APIs.
# ---------------------------------------------------------------------------
FRAMEWORKS: Tuple[Signature, ...] = (
    Signature("LangChain", AICategory.FRAMEWORK, patterns=(
        "from langchain", "langchain.chains", "langchain.chat_models",
        "@langchain/core", "@langchain/community", "ChatPromptTemplate(",
    )),
    Signature("LangGraph", AICategory.FRAMEWORK, patterns=(
        "from langgraph", "langgraph.graph", "@langchain/langgraph",
        "StateGraph(",
    )),
    Signature("LlamaIndex", AICategory.FRAMEWORK, patterns=(
        "from llama_index", "llama-index-core", "llamaindex.ts",
        "VectorStoreIndex(", "VectorStoreIndex.from_documents",
    )),
    Signature("Haystack", AICategory.FRAMEWORK, patterns=(
        "from haystack", "farm-haystack", "haystack.pipelines",
        "haystack.nodes",
    )),
    Signature("Semantic Kernel", AICategory.FRAMEWORK, patterns=(
        "microsoft.semantickernel", "semantic-kernel", "semantic_kernel",
        "kernelbuilder(",
    )),
    Signature("DSPy", AICategory.FRAMEWORK, patterns=(
        "import dspy", "dspy.Signature", "dspy.ChainOfThought",
        "dspy.Predict(",
    )),
    Signature("AutoGen", AICategory.FRAMEWORK, patterns=(
        "pyautogen", "import autogen", "autogen.AssistantAgent",
        "autogen.GroupChat(",
    )),
    Signature("CrewAI", AICategory.FRAMEWORK, patterns=(
        "from crewai", "crewai.Agent(", "crewai.Crew(", "crewai.Task(",
    )),
)

# ---------------------------------------------------------------------------
# AI SDKs -- client libraries for talking to a model provider.
# ---------------------------------------------------------------------------
SDKS: Tuple[Signature, ...] = (
    Signature("Vercel AI SDK", AICategory.SDK, patterns=(
        "@ai-sdk/", "ai/react", "ai/rsc", "useChat(", "useCompletion(",
        "streamText(", "generateText(",
    )),
    Signature("OpenAI SDK", AICategory.SDK, patterns=(
        "require('openai')", "require(\"openai\")", "from openai import OpenAI",
        "openai-python", "openai-node",
    )),
    Signature("Anthropic SDK", AICategory.SDK, patterns=(
        "@anthropic-ai/sdk", "anthropic-sdk-python", "anthropic-sdk-typescript",
    )),
    Signature("Google AI SDK", AICategory.SDK, patterns=(
        "@google/generative-ai", "google-generativeai", "google-genai",
    )),
    Signature("Hugging Face JS", AICategory.SDK, patterns=(
        "@huggingface/inference", "@huggingface/hub",
    )),
    Signature("Transformers.js", AICategory.SDK, patterns=(
        "@xenova/transformers", "transformers.js", "@huggingface/transformers",
    )),
)
