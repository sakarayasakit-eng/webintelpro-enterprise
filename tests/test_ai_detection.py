"""
Offline tests for Phase 2D AI Stack Detection.

This sub-system is passive-only (no probing mode at all, unlike API
discovery), so every test here is offline by construction. Coverage follows
the Phase 2D contract: provider/open-source-model/local-AI/framework/SDK/
vector-DB/embedding/infrastructure signature matching, confidence scoring via
the shared ConfidenceEngine, the guarantees that matter more than any single
detection (the default detect() path is unchanged, header *values* are never
inspected, generic prose does not false-trigger), and graceful degradation.
"""

from __future__ import annotations

from modules.ai_detection import AICategory, AIStackDetector
from modules.ai_detection.detector import ALL_SIGNATURES
from technology.detector import TechnologyDetector
from technology.parser import HTMLParser


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def analyze(html: str, headers=None, url: str = "https://site.test/"):
    """Run the AI-stack detection stage over raw HTML and return the analysis."""
    parsed = HTMLParser().parse(html)
    return AIStackDetector().analyze(parsed, url, headers)


def names(analysis):
    return {t.name for t in analysis.technologies}


def page(body: str, head: str = "") -> str:
    return f"<html><head>{head}</head><body>{body}</body></html>"


def script(js: str) -> str:
    return page(f"<script>{js}</script>")


# ---------------------------------------------------------------------------
# positive detections across categories
# ---------------------------------------------------------------------------

def test_detects_a_provider_from_api_host_and_sdk_import():
    html = script('const c = new OpenAI({apiKey: process.env.OPENAI_API_KEY});'
                  'fetch("https://api.openai.com/v1/chat/completions");')
    analysis = analyze(html)
    assert "OpenAI" in names(analysis)
    finding = next(f for f in analysis.report.findings if f.name == "OpenAI")
    assert finding.category is AICategory.PROVIDER


def test_detects_open_source_model_reference():
    html = script('const model = "meta-llama/Llama-3-70b-instruct";')
    analysis = analyze(html)
    assert "Llama" in names(analysis)
    finding = next(f for f in analysis.report.findings if f.name == "Llama")
    assert finding.category is AICategory.OPEN_SOURCE_MODEL


def test_detects_local_ai_runner():
    html = script('fetch("http://localhost:11434/api/chat");')
    analysis = analyze(html)
    assert "Ollama" in names(analysis)


def test_detects_ai_framework():
    html = script('import { StateGraph } from "@langchain/langgraph";')
    analysis = analyze(html)
    assert "LangGraph" in names(analysis)


def test_detects_ai_sdk():
    html = script('import { useChat } from "ai/react"; const {messages} = useChat();')
    analysis = analyze(html)
    assert "Vercel AI SDK" in names(analysis)


def test_detects_vector_database():
    html = script('const q = new QdrantClient({url: "http://localhost:6333"});')
    analysis = analyze(html)
    assert "Qdrant" in names(analysis)
    finding = next(f for f in analysis.report.findings if f.name == "Qdrant")
    assert finding.category is AICategory.VECTOR_DB


def test_detects_embedding_service():
    html = script('const r = await client.embeddings.create({model: '
                  '"text-embedding-3-small"});')
    analysis = analyze(html)
    assert "OpenAI Embeddings" in names(analysis)


def test_detects_ai_infrastructure():
    html = script('fetch("https://api.replicate.com/v1/predictions");'
                  'const REPLICATE_API_TOKEN = "x";')
    analysis = analyze(html)
    assert "Replicate" in names(analysis)


def test_detects_provider_via_response_header_name_only():
    analysis = analyze(page("<p>hi</p>"), headers={"anthropic-version": "2023-06-01"})
    assert "Anthropic" in names(analysis)
    finding = next(f for f in analysis.report.findings if f.name == "Anthropic")
    assert finding.evidence == ["anthropic-version"]


# ---------------------------------------------------------------------------
# mixed stack
# ---------------------------------------------------------------------------

def test_mixed_ai_stack_reports_every_category_present():
    html = script(
        'fetch("https://api.anthropic.com/v1/messages");'
        'import dspy;'
        'const q = new QdrantClient({url: "http://localhost:6333"});'
        'fetch("https://api.replicate.com/v1/predictions");'
    )
    analysis = analyze(html)
    found = names(analysis)
    assert {"Anthropic", "DSPy", "Qdrant", "Replicate"} <= found
    grouped = analysis.report.to_dict()
    assert len(grouped["providers"]) == 1
    assert len(grouped["frameworks"]) == 1
    assert len(grouped["vector_databases"]) == 1
    assert len(grouped["infrastructure"]) == 1


# ---------------------------------------------------------------------------
# negative detections / empty pages
# ---------------------------------------------------------------------------

def test_empty_page_yields_no_findings():
    analysis = analyze(page(""))
    assert analysis.technologies == []
    assert analysis.report.findings == []
    assert analysis.report.errors == []


def test_unrelated_page_yields_no_findings():
    html = page("<h1>Welcome to our bakery</h1><p>Fresh bread daily.</p>")
    analysis = analyze(html)
    assert analysis.technologies == []


# ---------------------------------------------------------------------------
# false-positive prevention
# ---------------------------------------------------------------------------

def test_generic_prose_does_not_false_trigger_model_family_names():
    """Bare dictionary/greek-letter words that happen to share a brand name
    (phi, falcon, gemma as ordinary prose) must not fire -- every real
    signature pattern is qualified (vendor- or version-scoped)."""
    html = page("<p>The golden ratio is called phi. A falcon flew over the "
               "gemma valley near the qwen river.</p>")
    analysis = analyze(html)
    assert names(analysis) == set()


def test_every_signature_pattern_is_qualified_not_a_bare_word():
    """Precision-over-recall guarantee at the data level: no pattern is a
    single plain dictionary word with no vendor/version/host qualifier that
    could match ordinary prose."""
    bare_dictionary_words = {
        "phi", "falcon", "gemma", "qwen", "llama", "mistral", "gemini",
        "cohere", "groq", "grok",
    }
    for sig in ALL_SIGNATURES:
        for pattern in sig.patterns:
            assert pattern.lower().strip() not in bare_dictionary_words, (
                f"{sig.name!r} has an unqualified bare-word pattern {pattern!r}")


def test_header_values_are_never_inspected_only_names():
    """A secret-looking header *value* must never itself cause a match --
    only the header *name* is compared against signature.headers."""
    analysis = analyze(page("<p>hi</p>"),
                       headers={"X-Custom": "sk-anthropic-super-secret-key"})
    assert names(analysis) == set()


# ---------------------------------------------------------------------------
# confidence scoring
# ---------------------------------------------------------------------------

def test_text_only_evidence_uses_ai_evidence_weight():
    analysis = analyze(script('fetch("https://api.groq.com/openai/v1/chat");'))
    finding = next(f for f in analysis.report.findings if f.name == "Groq")
    assert 0.30 <= finding.confidence < 0.60


def test_combining_header_and_text_evidence_raises_confidence():
    html = script('fetch("https://api.anthropic.com/v1/messages");')
    analysis = analyze(html, headers={"anthropic-version": "2023-06-01"})
    finding = next(f for f in analysis.report.findings if f.name == "Anthropic")
    text_only = analyze(html)
    text_only_finding = next(f for f in text_only.report.findings if f.name == "Anthropic")
    assert finding.confidence > text_only_finding.confidence


def test_low_confidence_findings_are_not_reported():
    from modules.ai_detection import AIDetectionConfig
    parsed = HTMLParser().parse(script('fetch("https://api.groq.com/openai/v1/chat");'))
    analysis = AIStackDetector(config=AIDetectionConfig(min_confidence=0.99)).analyze(
        parsed, "https://site.test/")
    assert analysis.technologies == []


# ---------------------------------------------------------------------------
# version extraction (reuses technology.version.VersionEngine, unmodified)
# ---------------------------------------------------------------------------

def test_dotted_model_version_is_extracted():
    analysis = analyze(script('fetch("https://generativelanguage.googleapis.com/'
                             'v1/models/gemini-1.5-pro:generateContent");'))
    finding = next(f for f in analysis.report.findings if f.name == "Google Gemini")
    assert finding.version == "1.5"


def test_hyphen_only_model_name_has_no_forced_version():
    analysis = analyze(script('console.log("using grok-beta");'))
    finding = next(f for f in analysis.report.findings if f.name == "xAI")
    assert finding.version is None


# ---------------------------------------------------------------------------
# report shape
# ---------------------------------------------------------------------------

def test_report_to_dict_has_every_category_key():
    grouped = analyze(page("<p>hi</p>")).report.to_dict()
    for cat in AICategory:
        assert cat.value in grouped
        assert grouped[cat.value] == []
    assert grouped["total_findings"] == 0


# ---------------------------------------------------------------------------
# TechnologyDetector integration
# ---------------------------------------------------------------------------

def test_default_detect_path_is_unaffected():
    html = script('fetch("https://api.openai.com/v1/chat/completions");')
    detector = TechnologyDetector()
    report = detector.detect("https://site.test/", html=html)
    assert report.ai_stack is None
    assert "ai_stack" not in report.to_dict()
    assert "OpenAI" not in {t.name for t in report.technologies}


def test_opt_in_detect_path_populates_report():
    html = script('fetch("https://api.openai.com/v1/chat/completions");'
                  'const c = new OpenAI({});')
    detector = TechnologyDetector()
    report = detector.detect("https://site.test/", html=html, analyze_ai_stack=True)
    assert report.ai_stack is not None
    assert report.ai_stack["total_findings"] >= 1
    assert any(t.category == "ai_providers" for t in report.technologies)
    assert "ai_stack" in report.to_dict()


def test_ai_detection_failure_degrades_gracefully(monkeypatch):
    detector = TechnologyDetector()

    class _Boom:
        def analyze(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(detector, "_ai_stack_detector", _Boom())
    report = detector.detect("https://site.test/", html=page("<p>hi</p>"),
                             analyze_ai_stack=True)
    assert report.ai_stack is None
    assert report.total_detected == len(report.technologies)  # did not crash
