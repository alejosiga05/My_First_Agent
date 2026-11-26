from pathlib import Path

from backend.retrieval import home_courses, load_documents, search

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "courses"


def docs_by_course():
    return {d.course: d for d in load_documents(FIXTURE_DIR)}


def test_header_lines_are_parsed():
    doc = docs_by_course()["Test Marketing"]

    assert doc.source_url == "https://example.org/cbs/marketing"
    assert doc.ects == 7.5
    assert doc.file == "tests/fixtures/courses/cbs_test_marketing.md"
    assert doc.side == "home"


def test_exchange_files_are_marked_exchange():
    assert docs_by_course()["Exchange Marketing"].side == "exchange"


def test_files_without_course_line_are_skipped():
    files = {d.file for d in load_documents(FIXTURE_DIR)}

    assert "tests/fixtures/courses/bocconi_test_catalogue.md" not in files


def test_home_courses_lists_only_home_side():
    names = home_courses(load_documents(FIXTURE_DIR))

    assert sorted(names) == ["Test Corporate Finance", "Test Marketing"]


def test_search_finds_relevant_exchange_course_first():
    docs = load_documents(FIXTURE_DIR)
    home = next(d for d in docs if d.course == "Test Marketing")

    results = search(home, docs, k=3)

    assert results[0].course == "Exchange Marketing"


def test_search_returns_only_exchange_chunks_with_citation():
    docs = load_documents(FIXTURE_DIR)
    home = next(d for d in docs if d.course == "Test Corporate Finance")

    results = search(home, docs, k=3)

    assert results
    for chunk in results:
        assert chunk.file.startswith("tests/fixtures/courses/bocconi_")
        assert chunk.source_url.startswith("https://example.org/bocconi/")
        assert chunk.ects is not None
        assert chunk.text


def test_search_groups_to_k_distinct_files():
    docs = load_documents(FIXTURE_DIR)
    home = next(d for d in docs if d.course == "Test Marketing")

    results = search(home, docs, k=2, per_file=2)

    assert len({c.file for c in results}) == 2
    for file in {c.file for c in results}:
        assert sum(c.file == file for c in results) <= 2
