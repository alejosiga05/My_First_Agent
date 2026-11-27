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
- 2026-11-27: Housing and Clubs & student life tabs, `POST /api/ask {section, question}`.
  `section` is `housing` or `clubs` (anything else 422); a blank question is 422. Response:
  `{section, found, answer, sources: [{file, title, url}], model_error}`. `title` is the file's `Topic:` line,
  `url` always the file's `Source:` line (never from the model).
- 2026-11-27: Info files are loaded by `load_info_documents` (any file with a `Source:` line, side `info`).
  `search_question` reuses the same TF-IDF ranking (`_rank`, shared with course `search`), only over the chosen
  section's folder. It returns the 3 best files with up to 20 chunks each (whole files in practice). Reason:
  with 2 chunks per file, real questions missed the answer because of different words ("cost" vs "Prices",
  "football" vs "Hobbies, Sports"). The folders are small (~8-9 KB each), so this costs ~2-3k tokens.
- 2026-11-27: `llm.answer_question` checks the model output in Python:
  sources not among the retrieved files are dropped; `found: true` with no valid source counts as not found;
  when not found the answer is replaced by "I don't know – please ask the Bocconi International Student Desk
  or Housing Office" and the page shows the closest retrieved files; model failure gives
  "Model unavailable – could not answer" (`model_error: true`).
- 2026-11-27: URL filter (`remove_unknown_urls`): a URL in the answer is kept only if it appears in the
  retrieved chunk text or is the `Source:` URL of a retrieved file; trailing punctuation and `/` are ignored
  when comparing. URLs without `http(s)://` or `www.` are not detected.
- 2026-11-27: The unused "Question" field was removed from the Courses form. `MatchRequest.question` stays
  optional in the backend (ignored), so old requests still work.

## Open questions

- Europe and Global Megatrends has no obvious Bocconi counterpart among the 8 profiles; expect "not sure".
- Housing data is a summary snapshot of Bocconi pages for Fall 2026-27; prices and dates change every year.
  Who refreshes it, and when?
- Answers in the Housing/Clubs tabs are not yet evaluated beyond the 6 suggested questions (checked by hand
  on 2026-11-27 with the real model).
