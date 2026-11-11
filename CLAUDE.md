# Course Exchange Assistant

## What this is

- Theory: students waste hours matching home and exchange courses; an LLM can read messy syllabi and exchange reports fast, but it invents details, so every course suggestion must cite a file in data/, and all credit maths is done in code.
- User: university students choosing which courses to take on an exchange semester.
- Done by 26 Nov: a student asks a question on the page and gets course suggestions with clickable sources from data/ and credit totals computed in Python; all tests pass.

## How to run it (Windows, from repo root)

- Create venv: `python -m venv .venv`
- Activate: PowerShell `.venv\Scripts\Activate.ps1` · Git Bash `source .venv/Scripts/activate`
- Install: `pip install -r requirements.txt`
- Start: `uvicorn backend.main:app --reload` → page at http://127.0.0.1:8000, health at /health
- Test: `pytest`

## Where things live

- backend/main.py: the only entry point; serves frontend/ and the API on one port.
- backend/llm.py: the only file that calls the model; it judges whether two courses match and returns the source it used.
- backend/retrieval.py: search over data/; every result keeps the file it came from.
- backend/recommender.py: ranking, credit (ECTS) totals and timetable clashes, in plain Python, using the matches from llm.py.
- frontend/: plain HTML, CSS and JavaScript. No framework, no build step.
- data/courses/: syllabi and course catalogues. data/exchange/: partner-university info and past-student reports. Read them, never modify them.
- tests/: every feature starts here with a failing test.
- tests/fixtures/: small sample syllabi for tests; tests never read data/.

## How to behave

1. Before editing, state your assumptions and a short plan; if the request is ambiguous, ask.
2. Make the smallest change that works; touch only the files the task needs.
3. Write the test first, then the code.
4. When done, say how you verified it: the command you ran and what it printed.
5. Record decisions and open questions in NOTES.md, not in this file.

## Rules for the app's LLM

- The model never does arithmetic, counting or dates; Python code computes them.
- If the answer is not in data/, the app says "not sure"; it never invents a course or a credit value.

## What not to do

- No new frameworks, no database, no login, no Docker.
- No features nobody asked for.
- Never edit a test to make it pass; fix the code instead.
- Never read, print or ask for .env; config is loaded in code with python-dotenv.
- Never add a second entry point or a second file that calls the model.

## Mistakes we have seen
<!-- One line per mistake: what went wrong → the rule. Empty for now. -->