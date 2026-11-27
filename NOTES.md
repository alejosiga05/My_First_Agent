# Notes

## Decisions

- 2026-11-23: "Not sure" matches are excluded from the confirmed ECTS total and shown separately
  (`summarize_credits` in recommender.py), so the page never overstates progress.
- 2026-11-26: Real data added: 6 CBS home courses (`cbs_*.md`) and 8 Bocconi profiles (`bocconi_30xxx_*.md`).
  The 3 SAMPLE demo files from 2026-11-23 were deleted. `/api/match` no longer reads tests/fixtures.
- 2026-11-26: Pipeline: retrieval.py (hand-written TF-IDF, stdlib only, chunks split at `## ` headings),
  then llm.py (content judgment only, JSON), then recommender.py (label + ECTS in Python).
  Retrieval sends the top 2 chunks from each of the 3 most relevant Bocconi files.
- 2026-11-26: Home vs exchange side is decided by filename prefix (`cbs_` / `bocconi_`, constants in retrieval.py).
- 2026-11-26: `bocconi_catalogue_fall_2026.md` is not indexed: it has no Course/ECTS line and only titles,
  so it cannot support a content match.
- 2026-11-26: Labels: `match` (content true, Bocconi ECTS >= home ECTS), `credit_gap` (content true,
  Bocconi ECTS < home ECTS; counts toward the total with its Bocconi ECTS), `not_sure` (content false;
  not counted). Course name, ECTS and Source URL on a card always come from the file, never from the model.
- 2026-11-26: A model answer citing a file outside the retrieved candidates is treated as content_match=false.
- 2026-11-26: Model failure (missing key, API error, bad JSON) gives a not_sure card with reason
  "Model unavailable – content could not be checked" and `model_error: true`; the server logs only the
  exception type, never the key or message.
- 2026-11-26: The form lists CBS courses as checkboxes from `GET /api/home-courses`; unknown names get 422.
- 2026-11-26: Model is `OPENAI_MODEL` from .env, default `gpt-4o-mini`.
- 2026-11-26: Deadline moved to 1 Dec. Timetable clashes dropped: we have no timetable data.
- 2026-11-27: Second home university: 6 WU Vienna files (`wu_*.md`). Home prefixes live in
  `HOME_UNIVERSITIES` in retrieval.py (`cbs_` -> "Copenhagen Business School", `wu_` -> "WU Vienna");
  the dropdown shows those short names, and each Document keeps its raw `University:` line in `university`.
- 2026-11-27: `GET /api/home-courses` returns `{"home_universities": [{"name", "courses"}]}` in that order.
  `/api/match` gives 422 for an unknown home university or a course from a different home university.
  Exchange university is fixed to "Bocconi University" on the page and not validated by the backend.
- 2026-11-27: not_sure cards get title "No clear match" and `closest_text` "Closest Bocconi course: <name>"
  (set in recommender.py), so they don't read as recommendations. Model-error cards use the same title.
- 2026-11-27: Summary field `unsure_ects` replaced by `not_sure_count` (number of home courses without a
  clear match), shown as "N courses without a clear match – ask your coordinator".

## Open questions

- Europe and Global Megatrends has no obvious Bocconi counterpart among the 8 profiles; expect "not sure".