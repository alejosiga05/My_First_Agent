"""Counting functions of scripts/evaluate.py, with hand-made results (no model, no data/)."""

import json
from pathlib import Path

from scripts import evaluate

EXPECTED_FILE = Path(__file__).parent / "eval" / "expected_matches.json"

CONTENT = {"home_university": "CBS", "home_course": "Finance", "accept": [{"bocconi": "Corporate Finance", "label": "content_match"}]}
MATCH = {"home_university": "WU", "home_course": "FM", "accept": [{"bocconi": "Corporate Finance", "label": "match"}]}
NOT_SURE = {"home_university": "CBS", "home_course": "Megatrends", "accept": [{"bocconi": None, "label": "not_sure"}]}
EITHER = {
    "home_university": "CBS",
    "home_course": "Strategy",
    "accept": [{"bocconi": "Business Strategy", "label": "content_match"}, {"bocconi": None, "label": "not_sure"}],
}
ANY = {"home_university": "WU", "home_course": "IFRS", "accept": "any"}


def result(bocconi, label, model_error=False):
    return {"bocconi": bocconi, "label": label, "model_error": model_error}


def test_content_match_accepts_match_and_credit_gap():
    assert evaluate.is_correct(CONTENT, result("Corporate Finance", "credit_gap")) is True
    assert evaluate.is_correct(CONTENT, result("Corporate Finance", "match")) is True
    assert evaluate.is_correct(CONTENT, result("Corporate Finance", "not_sure")) is False
    assert evaluate.is_correct(CONTENT, result("Corporate Valuation", "credit_gap")) is False


def test_match_does_not_accept_credit_gap():
    assert evaluate.is_correct(MATCH, result("Corporate Finance", "match")) is True
    assert evaluate.is_correct(MATCH, result("Corporate Finance", "credit_gap")) is False


def test_not_sure_ignores_the_closest_course():
    assert evaluate.is_correct(NOT_SURE, result("Business Strategy", "not_sure")) is True
    assert evaluate.is_correct(NOT_SURE, result("Business Strategy", "credit_gap")) is False


def test_two_acceptable_answers():
    assert evaluate.is_correct(EITHER, result("Business Strategy", "credit_gap")) is True
    assert evaluate.is_correct(EITHER, result("Marketing", "not_sure")) is True
    assert evaluate.is_correct(EITHER, result("Marketing", "credit_gap")) is False


def test_ambiguous_is_not_scored():
    assert evaluate.is_correct(ANY, result("Corporate Finance", "match")) is None


def test_model_error_is_wrong_even_for_not_sure():
    assert evaluate.is_correct(NOT_SURE, result(None, "not_sure", model_error=True)) is False


def test_accuracy_per_run_counts_clear_cases_only():
    rows = [
        {"expected": CONTENT, "runs": [result("Corporate Finance", "credit_gap")] * 2 + [result("Marketing", "credit_gap")]},
        {"expected": NOT_SURE, "runs": [result("Marketing", "not_sure")] * 3},
        {"expected": ANY, "runs": [result("Marketing", "not_sure")] * 3},
    ]

    assert evaluate.clear_count(rows) == 2
    assert evaluate.accuracy_per_run(rows) == [2, 2, 1]


def test_consistency_needs_same_course_and_label():
    same = [result("Marketing", "match")] * 3
    other_label = [result("Marketing", "match")] * 2 + [result("Marketing", "not_sure")]
    other_course = [result("Marketing", "match")] * 2 + [result("Marketing Research", "match")]

    assert evaluate.is_consistent(same) is True
    assert evaluate.is_consistent(other_label) is False
    assert evaluate.is_consistent(other_course) is False


def test_report_has_totals_and_one_row_per_course():
    rows = [
        {"expected": CONTENT, "runs": [result("Corporate Finance", "credit_gap")] * 3},
        {"expected": ANY, "runs": [result("Corporate Finance", "match")] * 2 + [result(None, "not_sure", True)]},
    ]

    report = evaluate.render_report(rows, model="test-model", today="2026-11-27")

    assert "Run 1: 1/1 clear cases correct" in report
    assert "Consistent across 3 runs: 1/2 courses" in report
    assert "test-model" in report
    assert sum(1 for line in report.splitlines() if line.startswith("| CBS |") or line.startswith("| WU |")) == 2
    assert "model error" in report


def test_expected_file_has_12_courses_and_9_clear_cases():
    entries = json.loads(EXPECTED_FILE.read_text(encoding="utf-8"))

    assert len(entries) == 12
    assert sum(1 for e in entries if e["accept"] != "any") == 9
