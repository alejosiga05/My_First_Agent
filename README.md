# Course Exchange Assistant

This assistant helps exchange students choose courses and find people who can advise them.
The language model explains and converses, while facts come from the documents in `data/`, always with citations.
Anything that must be exact, such as credits, ECTS and timetable clashes, is computed in code and never by the model.
Every model call goes through `backend/llm.py`, so there is a single place to control, test and replace it.
One FastAPI server delivers both the frontend and the API on one port, which keeps the system simple to run.
