# Exchange Student Assistant

This assistant helps exchange students prepare their semester at Bocconi. The page has three tabs:

- **Courses**: match home courses to Bocconi courses, with ECTS totals computed in code (`POST /api/match`).
- **Housing** and **Clubs & student life**: ask a question and get a short answer from our own documents in `data/housing/` and `data/clubs/`, with links to the official pages (`POST /api/ask`). If the documents don't answer it, the app says "I don't know" and points to the closest sources.

The language model explains and converses, while facts come from the documents in `data/`, always with citations.
Anything that must be exact, such as credits and ECTS, is computed in code and never by the model.
Every model call goes through `backend/llm.py`, so there is a single place to control, test and replace it.
One FastAPI server delivers both the frontend and the API on one port, which keeps the system simple to run.
