from app.semantic import evaluate_semantic_rules


def test_semantic_rules_expected_stdout():
    errs = evaluate_semantic_rules("42", 42, {"expected_stdout": "42"})
    assert not errs


def test_semantic_rules_expected_stdout_mismatch():
    errs = evaluate_semantic_rules("41", 41, {"expected_stdout": "42"})
    assert any("expected_stdout_mismatch" in e for e in errs)


def test_semantic_rules_expected_type_and_len_and_keys():
    value = [{"class": "A"}, {"class": "B"}]
    errs = evaluate_semantic_rules(
        "ignored",
        value,
        {"expected_type": "array", "expected_len": 2, "required_keys": ["class"]},
    )
    assert not errs


def test_semantic_rules_all_items_predicate_and_numeric_range():
    value = [{"score": 10}, {"score": 11}]
    errs = evaluate_semantic_rules(
        "ignored",
        value,
        {
            "all_items_predicate": "score >= 10",
            "numeric_range": {"path": "0.score", "min": 5, "max": 20},
        },
    )
    assert not errs
