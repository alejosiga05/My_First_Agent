# Notes

## Decisions

- 2026-11-23: `POST /api/match` returns fixed sample results from `tests/fixtures/sample_matches.json`
  (no model call) so the professor can review the UI. Replace with retrieval + llm.py later.
- 2026-11-23: One-time exception to "never modify data/": added 3 demo files
  (`data/courses/sample_exchange_catalogue.md`, `data/courses/sample_home_syllabus.md`,
  `data/exchange/sample_student_report.md`), each marked "SAMPLE". Delete them when real data arrives.
- 2026-11-23: "Not sure" matches are excluded from the confirmed ECTS total and shown separately
  (`summarize_credits` in recommender.py), so the page never overstates progress.

## Open questions

- Production code currently reads a file under tests/fixtures/; this goes away once real matching exists.
