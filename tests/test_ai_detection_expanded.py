"""
Offline tests for the AI Stack Detection quality audit.

Covers three things the original Phase 2D suite (tests/test_ai_detection.py)
didn't: (1) vendor *homepages* -- as opposed to third-party pages that
integrate a vendor's API -- now match via bare apex-domain evidence, (2)
brand-new signatures added to close explicit provider/framework/embedding/
vector-DB coverage gaps, (3) regression guards for the false-positive risks
identified and deliberately declined during the audit (x.ai substring
collision, Supabase's bare domain, ordinary-English hyphen prefixes).

``homepage()`` mirrors the markup shape every fetched vendor homepage
actually had during the audit: a canonical link, an OG tag and a copyright
footer, all carrying the bare apex domain -- never an API host or SDK import.
"""

from __future__ import annotations

import pytest

from modules.ai_detection import AIStackDetector
from modules.ai_detection.detector import ALL_SIGNATURES
from technology.parser import HTMLParser


def analyze(html: str, headers=None, url: str = "https://site.test/"):
    parsed = HTMLParser().parse(html)
    return AIStackDetector().analyze(parsed, url, headers)


def names(analysis):
    return {t.name for t in analysis.technologies}


def homepage(domain: str, brand: str) -> str:
    """A vendor's own marketing homepage: self-referential links only, no
    API host, no SDK import, no model-name string -- exactly what made these
    sites false negatives before this audit."""
    return (
        f'<html><head>'
        f'<link rel="canonical" href="https://www.{domain}/">'
        f'<meta property="og:url" content="https://www.{domain}/">'
        f'<meta property="og:site_name" content="{brand}">'
        f'</head><body>'
        f'<nav><a href="https://www.{domain}/pricing">Pricing</a></nav>'
        f'<footer>&copy; 2026 {brand}. All rights reserved. {domain}</footer>'
        f'</body></html>'
    )


# ---------------------------------------------------------------------------
# vendor homepages that were false negatives before the audit
# ---------------------------------------------------------------------------

HOMEPAGE_CASES = [
    ("anthropic.com", "Anthropic", "Anthropic"),
    ("mistral.ai", "Mistral AI", "Mistral AI"),
    ("cohere.com", "Cohere", "Cohere"),
    ("groq.com", "Groq", "Groq"),
    ("together.ai", "Together AI", "Together AI"),
    ("perplexity.ai", "Perplexity", "Perplexity"),
    ("fireworks.ai", "Fireworks AI", "Fireworks AI"),
    ("openrouter.ai", "OpenRouter", "OpenRouter"),
    ("deepseek.com", "DeepSeek", "DeepSeek"),
    ("huggingface.co", "Hugging Face", "Hugging Face"),
    ("openai.com", "OpenAI", "OpenAI"),
    ("ollama.com", "Ollama", "Ollama"),
    ("langchain.com", "LangChain", "LangChain"),
    ("llamaindex.ai", "LlamaIndex", "LlamaIndex"),
    ("weaviate.io", "Weaviate", "Weaviate"),
    ("milvus.io", "Milvus", "Milvus"),
    ("trychroma.com", "Chroma", "Chroma"),
    ("mastra.ai", "Mastra", "Mastra"),
]


@pytest.mark.parametrize("domain,brand,expected", HOMEPAGE_CASES)
def test_vendor_homepage_is_detected_via_self_domain(domain, brand, expected):
    analysis = analyze(homepage(domain, brand))
    assert expected in names(analysis), (
        f"{domain} homepage did not yield a {expected!r} finding; "
        f"got {names(analysis)}"
    )


def test_pydanticai_homepage_detected_via_doc_domain():
    html = homepage("ai.pydantic.dev", "PydanticAI")
    analysis = analyze(html)
    assert "PydanticAI" in names(analysis)


def test_vercel_ai_sdk_docs_domain_detected():
    html = homepage("ai-sdk.dev", "AI SDK")
    analysis = analyze(html)
    assert "Vercel AI SDK" in names(analysis)


# ---------------------------------------------------------------------------
# brand-new providers/frameworks/embeddings/vector-DBs added by the audit
# ---------------------------------------------------------------------------

def script(js: str) -> str:
    return f"<html><body><script>{js}</script></body></html>"


def test_detects_vertex_ai():
    html = script('fetch("https://us-central1-aiplatform.googleapis.com/v1/'
                  'projects/x/locations/us-central1/publishers/google/models/'
                  'gemini-1.5-pro:generateContent");')
    analysis = analyze(html)
    assert "Vertex AI" in names(analysis)


def test_detects_azure_openai():
    html = script('const client = new AzureOpenAI({endpoint: '
                  '"https://my-resource.openai.azure.com", '
                  'apiKey: process.env.AZURE_OPENAI_API_KEY});')
    analysis = analyze(html)
    assert "Azure OpenAI" in names(analysis)


def test_detects_fireworks_ai():
    html = script('fetch("https://api.fireworks.ai/inference/v1/chat/completions");')
    analysis = analyze(html)
    assert "Fireworks AI" in names(analysis)


def test_detects_openrouter():
    html = script('fetch("https://openrouter.ai/api/v1/chat/completions", '
                  '{headers: {Authorization: `Bearer ${OPENROUTER_API_KEY}`}});')
    analysis = analyze(html)
    assert "OpenRouter" in names(analysis)


def test_detects_hugging_face_provider():
    html = script('fetch("https://api-inference.huggingface.co/models/gpt2", '
                  '{headers: {Authorization: `Bearer ${HF_TOKEN}`}});')
    analysis = analyze(html)
    assert "Hugging Face" in names(analysis)


def test_detects_openai_agents_sdk():
    html = script('// pip install openai-agents\nfrom agents import Agent')
    analysis = analyze(html)
    assert "OpenAI Agents SDK" in names(analysis)


def test_detects_mastra():
    html = script('import { Mastra } from "@mastra/core"; const m = new Mastra({});')
    analysis = analyze(html)
    assert "Mastra" in names(analysis)


def test_detects_pydantic_ai():
    html = script('from pydantic_ai import Agent')
    analysis = analyze(html)
    assert "PydanticAI" in names(analysis)


def test_detects_faiss():
    html = script('// import faiss\nconst index = "IndexFlatL2(1536)";')
    analysis = analyze(html)
    assert "FAISS" in names(analysis)


def test_detects_lancedb():
    html = script('import lancedb from "@lancedb/lancedb"; '
                  'const db = lancedb.connect("./data");')
    analysis = analyze(html)
    assert "LanceDB" in names(analysis)


def test_detects_azure_ai_search():
    html = script('const client = new AzureSearch({endpoint: '
                  '"https://my-svc.search.windows.net"});')
    analysis = analyze(html)
    assert "Azure AI Search" in names(analysis)


def test_detects_supabase_vector_via_qualified_phrase():
    html = "<html><body><p>Store embeddings with Supabase Vector.</p></body></html>"
    analysis = analyze(html)
    assert "Supabase Vector" in names(analysis)


def test_detects_bge_embeddings():
    html = script('const model = "BAAI/bge-large-en-v1.5";')
    analysis = analyze(html)
    assert "BGE" in names(analysis)


def test_detects_sentence_transformers():
    html = script('# pip install sentence-transformers\n'
                  'model = SentenceTransformer("all-MiniLM-L6-v2")')
    analysis = analyze(html)
    assert "Sentence Transformers" in names(analysis)


# ---------------------------------------------------------------------------
# stale-model-slug freshness (durable hyphen-prefix patterns)
# ---------------------------------------------------------------------------

def test_current_claude_model_name_matches_via_durable_prefix():
    """Anthropic's own homepage advertises 'claude-sonnet-5', not the older
    'claude-3-5-sonnet' slug this signature used to match exclusively."""
    html = script('console.log("Now available: claude-sonnet-5");')
    analysis = analyze(html)
    assert "Anthropic" in names(analysis)


def test_current_grok_model_name_matches():
    html = script('console.log("grok-4 benchmark results");')
    analysis = analyze(html)
    assert "xAI" in names(analysis)


def test_current_deepseek_model_name_matches():
    html = script('console.log("deepseek-r1 reasoning model");')
    analysis = analyze(html)
    assert "DeepSeek" in names(analysis)


def test_current_mistral_model_name_matches():
    html = script('console.log("mistral-medium is our balanced model");')
    analysis = analyze(html)
    assert "Mistral AI" in names(analysis)


# ---------------------------------------------------------------------------
# false-positive regression guards for risks identified during the audit
# ---------------------------------------------------------------------------

def test_short_xai_domain_not_added_to_avoid_substring_collisions():
    """'x.ai' was deliberately excluded as a bare pattern: it is a substring
    of unrelated domains like 'netflix.ai' / 'relax.ai'. This guards against
    a future edit re-introducing it and silently reopening that hole."""
    xai_sig = next(s for s in ALL_SIGNATURES if s.name == "xAI")
    assert "x.ai" not in xai_sig.patterns


def test_unrelated_dot_ai_domain_does_not_trigger_xai():
    html = homepage("relax.ai", "Relax")
    analysis = analyze(html)
    assert "xAI" not in names(analysis)


def test_supabase_bare_domain_not_used_to_avoid_tagging_every_supabase_app():
    """Supabase is a general-purpose backend; only the qualified
    'Supabase Vector' phrasing/import should ever match, never the bare
    'supabase.com' domain that any Supabase customer's app would contain."""
    vector_sig = next(s for s in ALL_SIGNATURES if s.name == "Supabase Vector")
    assert not any(p.strip().lower() == "supabase.com" for p in vector_sig.patterns)


def test_ordinary_supabase_usage_is_not_tagged_as_ai_stack():
    html = homepage("supabase.com", "Supabase")  # no "vector" mention anywhere
    analysis = analyze(html)
    assert "Supabase Vector" not in names(analysis)


def test_cohere_command_prefix_stays_unqualified_not_added():
    """'command-' alone is ordinary English (command-line, command center)
    and must not be a pattern -- only the specific model-family slugs."""
    cohere_sig = next(s for s in ALL_SIGNATURES if s.name == "Cohere")
    assert "command-" not in cohere_sig.patterns


def test_perplexity_sonar_prefix_stays_unqualified_not_added():
    """'sonar-' alone collides with SonarQube and generic audio-sonar
    terminology -- only specific Perplexity model slugs are patterns."""
    perplexity_sig = next(s for s in ALL_SIGNATURES if s.name == "Perplexity")
    assert "sonar-" not in perplexity_sig.patterns


def test_sonarqube_mention_does_not_false_trigger_perplexity():
    html = "<html><body><p>We run SonarQube with a sonar-scanner CI job.</p></body></html>"
    analysis = analyze(html)
    assert "Perplexity" not in names(analysis)


def test_command_line_prose_does_not_false_trigger_cohere():
    html = ("<html><body><p>Run this from the command-line: the command-center "
            "dashboard updates live.</p></body></html>")
    analysis = analyze(html)
    assert "Cohere" not in names(analysis)


def test_every_new_pattern_is_still_qualified_not_a_bare_word():
    """Same data-level guarantee as the original Phase 2D suite, re-asserted
    here so it fails loudly if a future edit adds an unqualified brand word
    to any of the newly-added signatures."""
    bare_dictionary_words = {
        "phi", "falcon", "gemma", "qwen", "llama", "mistral", "gemini",
        "cohere", "groq", "grok", "openai", "anthropic", "claude", "deepseek",
        "ollama", "supabase", "chroma", "weaviate", "milvus", "faiss",
        "mastra", "command", "sonar",
    }
    for sig in ALL_SIGNATURES:
        for pattern in sig.patterns:
            assert pattern.lower().strip() not in bare_dictionary_words, (
                f"{sig.name!r} has an unqualified bare-word pattern {pattern!r}")


# ---------------------------------------------------------------------------
# no duplicate signature names across categories (would silently merge
# unrelated findings under one Technology key in TechnologyDetector.detect())
# ---------------------------------------------------------------------------

def test_no_duplicate_signature_names():
    seen = {}
    for sig in ALL_SIGNATURES:
        assert sig.name not in seen, (
            f"{sig.name!r} is defined twice: {sig.category} and {seen[sig.name]}")
        seen[sig.name] = sig.category
