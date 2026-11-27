# Exchange Student Assistant

This assistant helps exchange students prepare their semester at Bocconi. The page has three tabs:

- **Courses**: match home courses to Bocconi courses, with ECTS totals computed in code (`POST /api/match`).
- **Housing** and **Clubs & student life**: ask a question and get a short answer from our own documents in `data/housing/` and `data/clubs/`, with links to the official pages (`POST /api/ask`). If the documents don't answer it, the app says "I don't know" and points to the closest sources.

The language model explains and converses, while facts come from the documents in `data/`, always with citations.
Anything that must be exact, such as credits and ECTS, is computed in code and never by the model.
Every model call goes through `backend/llm.py`, so there is a single place to control, test and replace it.
One FastAPI server delivers both the frontend and the API on one port, which keeps the system simple to run.

## How we evaluated it

Students who did the exchange wrote down the expected Bocconi course for each of our 12 home courses
(6 CBS, 6 WU) in `tests/eval/expected_matches.json`. 9 are clear cases: a specific course, or "not sure" when no
Bocconi course fits. The other 3 are ambiguous, so any answer is accepted.

`scripts/evaluate.py` runs the real course-matching steps (retrieval, model judgment and recommender, without the
web page) 3 times for every course. All counting happens in Python. The script writes `eval_report.md` with:

- accuracy per run: how many of the 9 clear cases match what we expected;
- consistency: whether all 3 runs gave the same Bocconi course and label;
- a table with every course and its 3 results.

A CBS course is 7.5 ECTS and a Bocconi course is 6 ECTS, so a correct CBS match shows up as `credit_gap`
(same content, fewer credits), which we count as a content match.

To run it, start from the repo root with the venv active and `OPENAI_API_KEY` in `.env` (the script loads it with python-dotenv):

```
python scripts/evaluate.py
```

It makes 36 real model calls and is not part of `pytest`. Only its counting functions are tested, in `tests/test_evaluate.py`.
