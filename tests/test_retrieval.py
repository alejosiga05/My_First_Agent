from pathlib import Path

from backend.retrieval import (
    home_courses,
    home_courses_by_university,
    load_documents,
    load_info_documents,
    search,
    search_question,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "courses"
HOUSING_DIR = Path(__file__).parent / "fixtures" / "housing"


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

    assert sorted(names) == ["Test Corporate Finance", "Test IFRS Accounting", "Test Marketing"]


def test_wu_file_is_home_and_keeps_university_line():
    doc = docs_by_course()["Test IFRS Accounting"]

    assert doc.side == "home"
    assert doc.university == "Test Second Home School"
    assert doc.home_university == "WU Vienna"


def test_cbs_file_keeps_university_line():
    doc = docs_by_course()["Test Marketing"]

    assert doc.university == "Test Home School"
    assert doc.home_university == "Copenhagen Business School"


def test_exchange_file_has_no_home_university():
    assert docs_by_course()["Exchange Marketing"].home_university is None


def test_home_courses_grouped_by_university_in_fixed_order():
    grouped = home_courses_by_university(load_documents(FIXTURE_DIR))

    assert list(grouped) == ["Copenhagen Business School", "WU Vienna"]
    assert sorted(grouped["Copenhagen Business School"]) == ["Test Corporate Finance", "Test Marketing"]
    assert grouped["WU Vienna"] == ["Test IFRS Accounting"]


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


def test_info_documents_keep_source_and_topic():
    docs = {d.file: d for d in load_info_documents(HOUSING_DIR)}

    doc = docs["tests/fixtures/housing/test_exchange_housing.md"]
    assert doc.source_url == "https://example.org/housing/exchange"
    assert doc.course == "Test housing for exchange students"
    assert doc.ects is None
    assert set(docs) == {
        "tests/fixtures/housing/test_exchange_housing.md",
        "tests/fixtures/housing/test_private_housing.md",
    }


def test_search_question_ranks_the_relevant_file_first():
    docs = load_info_documents(HOUSING_DIR)

    chunks = search_question("How much do the residences cost for the semester?", docs)

    assert chunks[0].file == "tests/fixtures/housing/test_exchange_housing.md"
    assert any("EUR 4,000" in c.text for c in chunks)
    sources = {d.file: d.source_url for d in docs}
    assert all(c.source_url == sources[c.file] for c in chunks)
