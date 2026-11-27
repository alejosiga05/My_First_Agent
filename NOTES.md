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
- 2026-11-27: Model-free lists for the Housing and Clubs tabs, parsed in retrieval.py (`housing_websites`,
  `club_areas`, `start_here`); file paths are constants in main.py. No model call on any of them.
  - `GET /api/housing/websites` -> `{websites: [{name, url}], source: {file, title, url}, disclaimer}`, from the
    `## Websites` section of `bocconi_private_housing_websites.md` only (22 sites). The disclaimer
    "Listed by Bocconi – Bocconi does not guarantee these websites" is a fixed string in main.py.
  - `GET /api/clubs/areas` -> `{areas: [{name, clubs}], source}` from the `## ` headings of
    `bocconi_student_associations_list.md` (10 areas, 126 clubs). Headings in `NOT_AREAS`
    ("Tips for exchange students") are skipped. "Show clubs" filters this list on the page.
  - `GET /api/clubs/start-here` -> `{esn, fair}`: the `## ESN...` section of the community file (website =
    first URL on the Website line, Instagram handle, App line) and the "Associations on Display" bullet of the
    how-to-join file (its event URL is shown as a link, the "(source: ...)" part is cut from the text).
    The Instagram URL is built in code from the handle (`https://www.instagram.com/<handle>`); the file has no URL.
  - A missing file or section gives empty lists / `null` (200); the page then shows
    "Not sure – this list is not available."
  - Fixtures for these live in `tests/fixtures/lists/`, so the housing/clubs fixtures used by /api/ask
    retrieval tests are unchanged.
- 2026-11-27: `ANSWER_PROMPT` now says "If you name a website that appears in the text, include its URL
  exactly as written." The URL filter (`remove_unknown_urls`) is unchanged.
- 2026-11-27: "Your exchange profile" step above the tabs: study level (Bachelor/Master) and semester
  (Fall 2026/Spring 2027). Both optional, used only for warnings, never to filter or block results.
  - `/api/match` accepts optional `study_level` and `semester` (other values 422). Each card has `level_warning`:
    "Master course – check with your coordinator" when the student is Bachelor and the suggested course's
    `Level:` line (parsed into `Document.level`) is Graduate/Master/Postgraduate. Only `match`/`credit_gap`
    cards get it; a missing Level line gives no warning. `semester` is validated but not used by the backend.
  - Spring 2027 shows "Our data covers Fall 2026 only – check the official Bocconi catalogue for Spring" on the
    Courses and Housing tabs (fixed string in app.js; no data involved, so not in the backend).
  - Fixed line on the Courses tab: "All courses shown are taught in English. Course list: Bocconi Fall 2026
    catalogue; course descriptions from the 2025-26 course profiles." (the files' Note lines say 2025-2026).
- 2026-11-27: "Compare Bocconi exchange residences" panel at the top of the Housing tab (above the websites
  card, so "private housing websites below" is true). No model call.
  - `GET /api/housing/residences?max_budget=&within_5_min=&until=` -> `{residences: [{residence, room_type,
    monthly_price_eur, price_semester_eur, walking_time, period_text, bills_included, source}], date_warning,
    message}`. `max_budget` must be >= 0 and `until` an ISO date, otherwise 422. The file is
    `bocconi_exchange_residences_fall_2026.csv` (`RESIDENCES_FILE` in main.py), read by `retrieval.exchange_residences`.
    All maths is in `recommender.compare_residences`.
  - Months = whole calendar months from period_start to period_end (a partial last month is not counted; 24 Aug–24 Dec = 4).
    Monthly price = semester / months, rounded **half-up** to whole euros (4770/4 = 1192.5 -> 1193; `round()` would
    give 1192). Rows with a bad price or date, or with less than 1 month, are skipped.
  - Budget: rows with monthly price > budget are hidden (equal is kept).
  - "Within 5 minutes": the largest number before "minute" in `walking_time` must be <= 5
    ("within 10-15 minutes" -> 15 -> excluded). Text with no number is excluded when the box is ticked.
  - Date check: if `until` > the latest period_end, `date_warning` = "Exchange residences cover only <earliest start> –
    <latest end> – look at the private housing websites below". Rows stay visible (user's choice). The dates are
    formatted in Python with a fixed English month list.
  - Nothing left after the filters gives "No Bocconi exchange residence fits – try the private housing websites". A missing
    or empty file gives `residences: []` with no message, and the page shows "Not sure – this list is not available."
  - Fixture: `tests/fixtures/lists/test_exchange_residences.csv`; tests in `tests/test_residences.py`.

## Open questions

- The residences CSV covers Fall 2026 only (24 Aug – 24 Dec 2026). There is no Spring 2027 data. The Spring notice on the
  Housing tab already says so, but the table itself still shows the Fall rows.

- Europe and Global Megatrends has no obvious Bocconi counterpart among the 8 profiles; expect "not sure".
- Housing data is a summary snapshot of Bocconi pages for Fall 2026-27; prices and dates change every year.
  Who refreshes it, and when?
- Answers in the Housing/Clubs tabs are not yet evaluated beyond the 6 suggested questions (checked by hand
  on 2026-11-27 with the real model).
- All 8 real Bocconi course files say `Level: Undergraduate`, so the Master warning never shows on real data
  today; it is only covered by the `bocconi_test_graduate.md` fixture.
