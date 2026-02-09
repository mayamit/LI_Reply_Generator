"""Tests for the approve endpoint and generate→approve flow (Story 1.4)."""

from backend.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

VALID_GENERATE = {
    "context": {"post_text": "A" * 20, "preset_id": "prof_short_agree"},
    "preset_id": "prof_short_agree",
}


def _generate_draft() -> dict:
    """Generate a draft and return the response data."""
    resp = client.post("/api/v1/generate", json=VALID_GENERATE)
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["status"] == "success"
    assert data["record_id"] is not None
    return data


# ---------------------------------------------------------------------------
# AC1: Generated reply returned with record_id
# ---------------------------------------------------------------------------


class TestGenerateCreatesDraft:
    def test_generate_returns_record_id(self) -> None:
        data = _generate_draft()
        assert isinstance(data["record_id"], int)

    def test_generate_returns_reply_text(self) -> None:
        data = _generate_draft()
        assert len(data["result"]["reply_text"]) > 0


# ---------------------------------------------------------------------------
# AC5: Approve transitions to approved with confirmation
# ---------------------------------------------------------------------------


class TestApproveSuccess:
    def test_approve_returns_approved_status(self) -> None:
        data = _generate_draft()
        resp = client.post(
            "/api/v1/approve",
            json={"record_id": data["record_id"], "final_reply": "My polished reply."},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "approved"
        assert result["approved_at"] is not None
        assert result["record_id"] == data["record_id"]

    def test_approve_with_edited_text(self) -> None:
        data = _generate_draft()
        edited = "I edited this reply to match my voice."
        resp = client.post(
            "/api/v1/approve",
            json={"record_id": data["record_id"], "final_reply": edited},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# AC4: Empty reply blocks approval
# ---------------------------------------------------------------------------


class TestApproveEmptyBlocked:
    def test_empty_final_reply_rejected(self) -> None:
        data = _generate_draft()
        resp = client.post(
            "/api/v1/approve",
            json={"record_id": data["record_id"], "final_reply": ""},
        )
        assert resp.status_code == 422

    def test_whitespace_only_rejected(self) -> None:
        data = _generate_draft()
        resp = client.post(
            "/api/v1/approve",
            json={"record_id": data["record_id"], "final_reply": "   "},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC6: Double approve is idempotent
# ---------------------------------------------------------------------------


class TestApproveIdempotent:
    def test_double_approve_no_error(self) -> None:
        data = _generate_draft()
        record_id = data["record_id"]
        body = {"record_id": record_id, "final_reply": "Final version."}

        resp1 = client.post("/api/v1/approve", json=body)
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "approved"

        resp2 = client.post("/api/v1/approve", json=body)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "approved"
        # Same record, no duplication
        assert resp2.json()["record_id"] == record_id


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


class TestApproveNotFound:
    def test_approve_nonexistent_record(self) -> None:
        resp = client.post(
            "/api/v1/approve",
            json={"record_id": 999999, "final_reply": "Some text."},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Full flow: generate → approve
# ---------------------------------------------------------------------------


class TestFullFlow:
    def test_generate_then_approve(self) -> None:
        # Step 1: Generate
        data = _generate_draft()
        record_id = data["record_id"]
        reply_text = data["result"]["reply_text"]

        # Step 2: Approve with the generated text
        resp = client.post(
            "/api/v1/approve",
            json={"record_id": record_id, "final_reply": reply_text},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_generate_edit_then_approve(self) -> None:
        # Step 1: Generate
        data = _generate_draft()
        record_id = data["record_id"]

        # Step 2: "Edit" — user changes the text
        edited = "Completely rewritten by the user."

        # Step 3: Approve with edited text
        resp = client.post(
            "/api/v1/approve",
            json={"record_id": record_id, "final_reply": edited},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
