# Course Exchange Assistant

## What this is

- Theory: students waste hours matching home and exchange courses and hunting for housing and club info; an LLM can read messy syllabi, exchange reports and university pages fast, but it invents details, so every suggestion or answer must cite a file in data/, and all credit maths is done in code.
- User: university students preparing an exchange semester: which courses to take (Courses tab), where to live (Housing tab) and which clubs to join or how to meet people (Clubs & student life tab).
- Done by 1 Dec: a student asks a question on the page and gets course suggestions with clickable sources from data/ and credit totals computed in Python; all tests pass.

## How to run it (Windows, from repo root)

- Create venv: `python -m venv .venv`
- Activate: PowerShell `.venv\Scripts\Activate.ps1` · Git Bash `source .venv/Scripts/activate`
- Install: `pip install -r requirements.txt`
- Start: `uvicorn backend.main:app --reload` → page at http://127.0.0.1:8000, health at /health
- Test: `pytest`

## Where things live

- backend/main.py: the only entry point; serves frontend/ and the API on one port.
- backend/llm.py: the only file that calls the model; it judges whether two courses match and returns the source it used, and answers Housing/Clubs questions only from retrieved text (URL and source checks happen here, in Python).
- backend/retrieval.py: search over data/ (courses, and per-section search for housing/clubs); every result keeps the file it came from and its Source URL.
- backend/recommender.py: ranking, credit (ECTS) totals and match labels, in plain Python, using the matches from llm.py.
- frontend/: plain HTML, CSS and JavaScript. No framework, no build step.
- data/courses/: syllabi and course catalogues. data/exchange/: partner-university info and past-student reports.
- data/housing/: Bocconi housing pages (exchange residences, prices, private-housing websites). data/clubs/: student associations, how to join, official channels for international students. Each starts with Source/University/Topic lines.
- Read everything in data/, never modify it.
- tests/: every feature starts here with a failing test.
- tests/fixtures/: small sample syllabi (courses/), housing and clubs files for tests; tests never read data/.

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