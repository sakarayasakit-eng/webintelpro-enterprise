from technology.confidence import ConfidenceEngine
from technology.rules import RuleResult


def _result(matched, evidence):
    return RuleResult(matched=matched, evidence=evidence, contexts=[])


def test_no_match_is_zero():
    assert ConfidenceEngine().calculate({}) == 0.0
    assert ConfidenceEngine().calculate(
        {"scripts": _result(False, [])}
    ) == 0.0


def test_single_signal_uses_base_weight():
    engine = ConfidenceEngine()
    score = engine.calculate({"headers": _result(True, ["x-powered-by"])})
    assert score == engine.WEIGHTS["headers"]


def test_extra_evidence_in_same_source_increases_confidence():
    engine = ConfidenceEngine()
    one = engine.calculate({"scripts": _result(True, ["a.js"])})
    two = engine.calculate({"scripts": _result(True, ["a.js", "b.js"])})
    three = engine.calculate({"scripts": _result(True, ["a.js", "b.js", "c.js"])})
    assert one < two < three


def test_extra_evidence_is_capped():
    engine = ConfidenceEngine()
    many = ["s%d.js" % i for i in range(20)]
    capped_at_cap = engine.calculate(
        {"scripts": _result(True, many[: engine.MAX_EXTRA_PER_SOURCE + 1])}
    )
    with_more = engine.calculate({"scripts": _result(True, many)})
    assert capped_at_cap == with_more


def test_duplicate_evidence_values_dont_double_count():
    engine = ConfidenceEngine()
    dup = engine.calculate({"scripts": _result(True, ["a.js", "a.js"])})
    single = engine.calculate({"scripts": _result(True, ["a.js"])})
    assert dup == single


def test_multiple_sources_combine_higher_than_any_single_source():
    engine = ConfidenceEngine()
    combined = engine.calculate({
        "headers": _result(True, ["x-powered-by"]),
        "cookies": _result(True, ["session"]),
    })
    assert combined > engine.WEIGHTS["headers"]
    assert combined > engine.WEIGHTS["cookies"]
