"""Tests for the POST /api/v1/post-context endpoint."""

from backend.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

VALID_MINIMAL = {"post_text": "A" * 20, "preset_id": "prof_short_agree"}


# --- Success cases ---


def test_post_context_minimal() -> None:
    resp = client.post("/api/v1/post-context", json=VALID_MINIMAL)
    assert resp.status_code == 200
    data = resp.json()
    assert data["preset_label"] == "Professional – Short Agreement"
    assert data["tone"] == "professional"
    assert data["validation_warnings"] == []


def test_post_context_complete() -> None:
    body = {
        **VALID_MINIMAL,
        "author_name": "Jane Doe",
        "author_profile_url": "https://linkedin.com/in/janedoe",
        "post_url": "https://linkedin.com/posts/abc",
        "article_text": "Some article body.",
        "image_ref": "sunset.jpg",
    }
    resp = client.post("/api/v1/post-context", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["author_name"] == "Jane Doe"


# --- 422 error cases ---


def test_missing_post_text() -> None:
    resp = client.post("/api/v1/post-context", json={"preset_id": "prof_short_agree"})
    assert resp.status_code == 422


def test_short_post_text() -> None:
    resp = client.post(
        "/api/v1/post-context",
        json={"post_text": "short", "preset_id": "prof_short_agree"},
    )
    assert resp.status_code == 422


def test_invalid_preset() -> None:
    resp = client.post(
        "/api/v1/post-context",
        json={"post_text": "A" * 20, "preset_id": "does_not_exist"},
    )
    assert resp.status_code == 422
    assert "Unknown preset_id" in str(resp.json())


def test_long_url_rejected() -> None:
    resp = client.post(
        "/api/v1/post-context",
        json={
            **VALID_MINIMAL,
            "author_profile_url": "https://example.com/" + "a" * 2_000,
        },
    )
    assert resp.status_code == 422


# --- 200 with warnings ---


def test_non_linkedin_url_returns_warning() -> None:
    resp = client.post(
        "/api/v1/post-context",
        json={
            **VALID_MINIMAL,
            "post_url": "https://twitter.com/status/123",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["validation_warnings"]) == 1
    assert "not appear to be a LinkedIn link" in data["validation_warnings"][0]
