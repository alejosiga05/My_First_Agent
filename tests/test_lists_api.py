"""Model-free lists for the Housing and Clubs tabs. Files come from tests/fixtures/lists; the model is never called."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import llm, main, retrieval
from backend.main import app

LISTS = Path(__file__).parent / "fixtures" / "lists"
WEBSITES = LISTS / "test_housing_websites.md"
ASSOCIATIONS = LISTS / "test_associations_list.md"
COMMUNITY = LISTS / "test_community.md"
JOIN = LISTS / "test_join_associations.md"
MISSING = LISTS / "does_not_exist.md"

client = TestClient(app)


@pytest.fixture(autouse=True)
def fixture_files_and_no_model(monkeypatch):
    monkeypatch.setattr(main, "HOUSING_WEBSITES_FILE", WEBSITES)
    monkeypatch.setattr(main, "CLUBS_LIST_FILE", ASSOCIATIONS)
    monkeypatch.setattr(main, "CLUBS_COMMUNITY_FILE", COMMUNITY)
    monkeypatch.setattr(main, "CLUBS_JOIN_FILE", JOIN)

    def no_model():
        raise AssertionError("the model must not be called")

    monkeypatch.setattr(llm, "_client", no_model)


# --- Parsers ---


def test_websites_come_from_the_websites_section_in_file_order():
    result = retrieval.housing_websites(WEBSITES)

    assert result["websites"] == [
        {"name": "Flat Finder", "url": "https://www.flatfinder.example.com"},
        {"name": "Room Hub", "url": "https://roomhub.example.com"},
        {"name": "Stay Local", "url": "https://staylocal.example.com/en"},
    ]
    assert result["source"] == {
        "file": "tests/fixtures/lists/test_housing_websites.md",
        "title": "Test websites for private housing",
        "url": "https://example.org/housing/websites",
    }


def test_club_areas_in_file_order_without_tips():
    result = retrieval.club_areas(ASSOCIATIONS)

    assert result["areas"] == [
        {"name": "Finance", "clubs": ["Test Finance Club", "Test Investment Society"]},
        {"name": "Sport", "clubs": ["Test Football Team", "Test Rowing Club"]},
    ]
    assert result["source"]["url"] == "https://example.org/clubs/official-list"
    assert result["source"]["title"] == "Test list of associations by topic area"


def test_start_here_takes_links_from_the_files():
    result = retrieval.start_here(COMMUNITY, JOIN)

    esn = result["esn"]
    assert esn["name"] == "ESN Test (Erasmus Student Network)"
    assert esn["website"] == "https://test.esn.example.org"
    assert esn["instagram"] == {"handle": "@esntest", "url": "https://www.instagram.com/esntest"}
    assert esn["app"] == "ESNapp (follow ESN Test)"
    assert esn["source"]["url"] == "https://example.org/esn"

    fair = result["fair"]
    assert "Associations on Display" in fair["text"]
    assert "September and in February" in fair["text"]
    assert "(source:" not in fair["text"]
    assert fair["event_url"] == "https://example.org/events/aod"
    assert fair["source"]["url"] == "https://example.org/clubs/how-to-join"


def test_missing_section_or_file_gives_empty_results():
    assert retrieval.housing_websites(COMMUNITY)["websites"] == []
    assert retrieval.housing_websites(MISSING) == {"websites": [], "source": None}
    assert retrieval.club_areas(MISSING) == {"areas": [], "source": None}
    assert retrieval.start_here(MISSING, MISSING) == {"esn": None, "fair": None}
    assert retrieval.start_here(WEBSITES, WEBSITES) == {"esn": None, "fair": None}


# --- Endpoints ---


def test_housing_websites_endpoint():
    response = client.get("/api/housing/websites")

    assert response.status_code == 200
    body = response.json()
    assert [w["name"] for w in body["websites"]] == ["Flat Finder", "Room Hub", "Stay Local"]
    assert body["disclaimer"] == "Listed by Bocconi – Bocconi does not guarantee these websites"
    assert body["source"]["url"] == "https://example.org/housing/websites"


def test_club_areas_endpoint():
    response = client.get("/api/clubs/areas")

    assert response.status_code == 200
    body = response.json()
    assert [a["name"] for a in body["areas"]] == ["Finance", "Sport"]
    assert body["source"]["url"] == "https://example.org/clubs/official-list"


def test_start_here_endpoint():
    response = client.get("/api/clubs/start-here")

    assert response.status_code == 200
    body = response.json()
    assert body["esn"]["website"] == "https://test.esn.example.org"
    assert body["fair"]["event_url"] == "https://example.org/events/aod"


def test_endpoints_with_missing_files_return_empty_lists(monkeypatch):
    monkeypatch.setattr(main, "HOUSING_WEBSITES_FILE", MISSING)
    monkeypatch.setattr(main, "CLUBS_LIST_FILE", MISSING)
    monkeypatch.setattr(main, "CLUBS_COMMUNITY_FILE", MISSING)
    monkeypatch.setattr(main, "CLUBS_JOIN_FILE", MISSING)

    assert client.get("/api/housing/websites").json()["websites"] == []
    assert client.get("/api/clubs/areas").json()["areas"] == []
    assert client.get("/api/clubs/start-here").json() == {"esn": None, "fair": None}
