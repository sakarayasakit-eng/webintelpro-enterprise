"""Offline tests for canonical / query-variant / internal-link analysis."""

from modules import indexability as idx


def _page(url, canonical="", noindex=False, query=None):
    from urllib.parse import urlparse
    q = query if query is not None else urlparse(url).query
    return {"url": url, "query": q, "canonical": canonical, "noindex": noindex}


def test_query_variants_converge_on_canonical():
    pages = [
        _page("https://x.com/?cur=AED", canonical="https://x.com/"),
        _page("https://x.com/?cur=USD", canonical="https://x.com/"),
        _page("https://x.com/?cur=GBP", canonical="https://x.com/"),
    ]
    res = idx.analyze_query_variants(pages)
    assert res["paths_with_query_variants"] == 1
    g = res["groups"][0]
    assert g["canonicalizes_to_single_url"] is True
    assert g["risk"] == "LOW"


def test_query_variants_no_canonical_is_risky():
    pages = [_page(f"https://x.com/?cur={c}") for c in ["AED", "USD", "GBP", "EUR"]]
    res = idx.analyze_query_variants(pages)
    g = res["groups"][0]
    assert g["canonicalizes_to_single_url"] is False
    assert g["risk"] in ("MEDIUM", "HIGH")
    assert g["confidence"] == "likely"


def test_query_variants_conflicting_canonicals():
    pages = [
        _page("https://x.com/?cur=AED", canonical="https://x.com/?cur=AED"),
        _page("https://x.com/?cur=USD", canonical="https://x.com/?cur=USD"),
    ]
    res = idx.analyze_query_variants(pages)
    g = res["groups"][0]
    assert g["risk"] == "MEDIUM"
    assert g["canonicalizes_to_single_url"] is False


def test_canonicals_self_and_missing():
    pages = [
        _page("https://x.com/a", canonical="https://x.com/a"),
        _page("https://x.com/b", canonical=""),
        _page("https://x.com/c", noindex=True),
    ]
    res = idx.analyze_canonicals(pages)
    assert res["self_canonical_count"] == 1
    assert res["no_canonical_count"] == 2  # b has none; c has none either
    assert "https://x.com/c" in res["pages_with_noindex"]


def test_canonicals_unreciprocated():
    pages = [
        _page("https://x.com/dup1", canonical="https://x.com/main"),
        _page("https://x.com/main", canonical="https://x.com/other"),  # doesn't point to itself
    ]
    res = idx.analyze_canonicals(pages)
    assert len(res["unreciprocated_canonicals"]) == 1


def test_internal_links_weakly_linked():
    pages = [_page("https://x.com/"), _page("https://x.com/orphanish")]
    link_graph = {"https://x.com": {"https://x.com/other"}}  # nothing links to /orphanish
    res = idx.analyze_internal_links(pages, link_graph)
    assert res["available"] is True
    urls = {r["url"] for r in res["weakly_linked_sample"]}
    assert "https://x.com/orphanish" in urls


def test_internal_links_unavailable_when_no_graph():
    res = idx.analyze_internal_links([_page("https://x.com/")], {})
    assert res["available"] is False


def test_run_combines_all():
    pages = [_page("https://x.com/", canonical="https://x.com/")]
    res = idx.run(pages, "https://x.com/", {})
    assert set(res.keys()) == {"query_variants", "canonicals", "internal_links"}
