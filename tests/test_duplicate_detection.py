"""Offline tests for k-shingle near-duplicate content clustering."""

from modules import duplicate_detection as dd


def _html(text):
    return f"<html><body><p>{text}</p></body></html>"


def test_extract_text_strips_script_and_style():
    html = "<html><body><script>var x=1;</script><style>.a{}</style><p>Hello world</p></body></html>"
    text = dd.extract_text(html)
    assert "Hello world" in text
    assert "var x" not in text
    assert ".a{}" not in text


def test_shingle_set_basic():
    s1 = dd.shingle_set("the quick brown fox jumps over the lazy dog")
    s2 = dd.shingle_set("the quick brown fox jumps over the lazy dog")
    assert s1 == s2
    assert len(s1) > 0


def test_jaccard_identical_and_disjoint():
    a = {1, 2, 3}
    b = {1, 2, 3}
    assert dd.jaccard(a, b) == 1.0
    c = {4, 5, 6}
    assert dd.jaccard(a, c) == 0.0


def test_cluster_pages_finds_near_duplicates():
    base = ("Home loan calculator for {c}. Enter your loan amount, interest rate, "
            "and tenure to calculate your monthly EMI instantly using our free tool "
            "designed for homebuyers across the region who need accurate estimates.")
    pages = [
        {"url": f"https://x.com/loan-{c}",
         "shingles": dd.shingle_set(base.format(c=c)),
         "word_count": len(base.split())}
        for c in ["uae", "usa", "uk", "india"]
    ]
    pages.append({"url": "https://x.com/about",
                  "shingles": dd.shingle_set("Our company was founded in 2010 to help "
                                              "people make better financial decisions "
                                              "through education and free tools."),
                  "word_count": 20})
    clusters = dd.cluster_pages(pages, threshold=0.5)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["size"] == 4
    assert "about" not in cluster["pages"][0]
    assert cluster["confidence"] == "heuristic"
    assert cluster["risk"] in ("HIGH", "MEDIUM")


def test_cluster_pages_no_clusters_when_all_different():
    pages = [
        {"url": "https://x.com/a", "shingles": dd.shingle_set("alpha beta gamma delta epsilon zeta"), "word_count": 6},
        {"url": "https://x.com/b", "shingles": dd.shingle_set("one two three four five six seven"), "word_count": 7},
    ]
    clusters = dd.cluster_pages(pages)
    assert clusters == []


def test_summarize():
    clusters = [{"risk": "HIGH", "pages": ["a", "b"]}, {"risk": "LOW", "pages": ["c", "d"]}]
    s = dd.summarize(clusters, total_pages=10)
    assert s["clusters_found"] == 2
    assert s["high_risk_clusters"] == 1
    assert s["low_risk_clusters"] == 1
    assert s["pages_in_any_cluster"] == 4
    assert s["pages_unclustered"] == 6
