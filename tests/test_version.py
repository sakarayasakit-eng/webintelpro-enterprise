from technology.detector import TechnologyDetector
from technology.version import VersionEngine


def test_dotted_version_immediately_after_match():
    v = VersionEngine()
    assert v.extract("wordpress 6.4") == "6.4"
    assert v.extract("nginx/1.25.3 x-powered-by:php/8.2") == "1.25.3"


def test_keyword_version_found_anywhere_in_context():
    v = VersionEngine()
    assert v.extract("acme-widget stuff... version: 2.3.1") == "2.3.1"
    assert v.extract("jquery core /*! jQuery v3.6.0 | (c) OpenJS */") == "3.6.0"


def test_distant_unrelated_number_not_picked_as_version():
    v = VersionEngine()
    # The real signal has no version; a decimal-looking number 40+ chars
    # away (e.g. a price or an unrelated id) must not be mistaken for one.
    text = "acmecms loaded ok, see pricing at 12.99 dollars for plan " + ("x" * 20)
    assert v.extract(text) is None


def test_rejects_implausible_versions():
    v = VersionEngine()
    assert v.extract("thing 0.0.0 rest") is None          # all-zero
    assert v.extract("thing 170141183.1 rest") is None      # component too long
    assert v.extract("thing 42 rest") is None               # no dot at all


def test_version_extraction_end_to_end():
    d = TechnologyDetector()
    r = d.detect(
        "https://x.example",
        '<meta name="generator" content="WordPress 6.4">',
        {"Server": "nginx/1.25.3"},
        {},
    )
    versions = {t.name: t.version for t in r.technologies}
    assert versions.get("WordPress") == "6.4"
    assert versions.get("Nginx") == "1.25.3"
