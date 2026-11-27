"""Evaluate course matching with the real model: accuracy on clear cases and consistency over 3 runs.

Run from the repo root (venv active, key in .env):  python scripts/evaluate.py
Writes eval_report.md. Not part of pytest. All counting is done here, in Python.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
EXPECTED_FILE = ROOT_DIR / "tests" / "eval" / "expected_matches.json"
REPORT_FILE = ROOT_DIR / "eval_report.md"
RUNS = 3

CONTENT_LABELS = {"match", "credit_gap"}  # CBS 7.5 ECTS vs Bocconi 6 ECTS: a right match shows as credit_gap
SHORT_UNI = {"Copenhagen Business School": "CBS", "WU Vienna": "WU"}


def load_expected(path: Path = EXPECTED_FILE) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _accepts(option: dict, res: dict) -> bool:
    if option["label"] == "not_sure":
        return res["label"] == "not_sure"
    labels = CONTENT_LABELS if option["label"] == "content_match" else {option["label"]}
    return res["label"] in labels and res["bocconi"] == option["bocconi"]


def is_correct(expected: dict, res: dict) -> bool | None:
    """True/False for a clear case; None for an ambiguous one (any answer accepted, not scored)."""
    if expected["accept"] == "any":
        return None
    if res["model_error"]:
        return False
    return any(_accepts(option, res) for option in expected["accept"])


def clear_count(rows: list[dict]) -> int:
    return sum(1 for row in rows if row["expected"]["accept"] != "any")


def accuracy_per_run(rows: list[dict]) -> list[int]:
    runs = len(rows[0]["runs"]) if rows else 0
    return [sum(1 for row in rows if is_correct(row["expected"], row["runs"][i]) is True) for i in range(runs)]


def is_consistent(runs: list[dict]) -> bool:
    return len({(r["bocconi"], r["label"]) for r in runs}) == 1


def _expected_text(expected: dict) -> str:
    if expected["accept"] == "any":
        return "any (ambiguous)"
    return " or ".join(
        "not_sure" if o["label"] == "not_sure" else f"{o['bocconi']} ({o['label']})" for o in expected["accept"]
    )


def _result_text(res: dict) -> str:
    if res["model_error"]:
        return "model error"
    return f"{res['bocconi'] or '–'} ({res['label']})"


def _correct_text(expected: dict, runs: list[dict]) -> str:
    marks = [is_correct(expected, r) for r in runs]
    if marks[0] is None:
        return "–"
    return f"{sum(1 for m in marks if m)}/{len(marks)}"


def render_report(rows: list[dict], model: str, today: str) -> str:
    clear = clear_count(rows)
    consistent = sum(1 for row in rows if is_consistent(row["runs"]))
    errors = sum(1 for row in rows for r in row["runs"] if r["model_error"])
    lines = [
        "# Course matching evaluation",
        "",
        f"Model: {model} · Date: {today} · {len(rows)} home courses × {len(rows[0]['runs']) if rows else 0} runs",
        "",
        "## Accuracy on clear cases",
        "",
    ]
    lines += [f"- Run {i + 1}: {n}/{clear} clear cases correct" for i, n in enumerate(accuracy_per_run(rows))]
    lines += [
        "",
        "## Consistency",
        "",
        f"- Consistent across {len(rows[0]['runs']) if rows else 0} runs: {consistent}/{len(rows)} courses "
        "(same Bocconi course and label every run)",
        f"- Runs with a model error: {errors}",
        "",
        "## All results",
        "",
        "For not_sure, the course shown is only the closest Bocconi course. "
        "content_match = match or credit_gap (same content; credit_gap means fewer ECTS).",
        "",
        "| Uni | Home course | Expected | " + " | ".join(f"Run {i + 1}" for i in range(len(rows[0]["runs"]) if rows else 0))
        + " | Agree? | Correct |",
        "|" + "---|" * (6 + (len(rows[0]["runs"]) if rows else 0) - 1),
    ]
    for row in rows:
        exp = row["expected"]
        cells = [
            SHORT_UNI.get(exp["home_university"], exp["home_university"]),
            exp["home_course"],
            _expected_text(exp),
            *(_result_text(r) for r in row["runs"]),
            "yes" if is_consistent(row["runs"]) else "no",
            _correct_text(exp, row["runs"]),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def run_once(home, docs, by_file) -> dict:
    """Same steps as /api/match in backend/main.py: retrieval -> llm -> recommender."""
    from backend import llm, retrieval
    from backend.recommender import build_card

    candidates = retrieval.search(home, docs)
    judgment = llm.judge_match(home, candidates)
    chosen = judgment.get("source_file") or (candidates[0].file if candidates else None)
    card = build_card(judgment, home, by_file.get(chosen))
    return {"bocconi": card["exchange_course"], "label": card["label"], "model_error": card["model_error"]}


def main() -> None:
    sys.path.insert(0, str(ROOT_DIR))
    from dotenv import load_dotenv

    from backend import llm, retrieval

    load_dotenv(ROOT_DIR / ".env")
    docs = retrieval.load_documents(ROOT_DIR / "data" / "courses")
    homes = {(d.home_university, d.course): d for d in docs if d.side == "home"}
    by_file = {d.file: d for d in docs}

    expected = load_expected()
    missing = [e["home_course"] for e in expected if (e["home_university"], e["home_course"]) not in homes]
    if missing:
        sys.exit(f"Not found in data/courses: {', '.join(missing)}")

    rows = []
    for exp in expected:
        home = homes[(exp["home_university"], exp["home_course"])]
        runs = [run_once(home, docs, by_file) for _ in range(RUNS)]
        print(f"{exp['home_course']}: " + " | ".join(_result_text(r) for r in runs))
        rows.append({"expected": exp, "runs": runs})

    model = os.getenv("OPENAI_MODEL") or llm.DEFAULT_MODEL
    report = render_report(rows, model=model, today=date.today().isoformat())
    REPORT_FILE.write_text(report, encoding="utf-8")
    print()
    for i, n in enumerate(accuracy_per_run(rows)):
        print(f"Run {i + 1}: {n}/{clear_count(rows)} clear cases correct")
    print(f"Consistent: {sum(1 for row in rows if is_consistent(row['runs']))}/{len(rows)} courses")
    print(f"Report written to {REPORT_FILE.name}")


if __name__ == "__main__":
    main()
