"""Tests for preset selection and defaulting behavior (Story 2.2).

Covers all 5 acceptance criteria:
  AC1: Valid preset_id → corresponding preset used
  AC2: Missing/null preset_id → default preset used
  AC3: Invalid preset_id → generation blocked with error
  AC4: Default preset always available and stable
  AC5: Different presets reflected in prompt assembly
"""

from backend.app.main import app
from backend.app.models.presets import get_default_preset, get_preset_by_id
from backend.app.services.prompt_builder import build_prompt
from backend.app.services.validation import validate_and_build_payload
from fastapi.testclient import TestClient

client = TestClient(app)

MINIMAL_CONTEXT = {"post_text": "A" * 20, "preset_id": "prof_short_agree"}


# ---------------------------------------------------------------------------
# AC1: Valid preset_id → corresponding preset used
# ---------------------------------------------------------------------------


class TestValidPresetSelection:
    def test_valid_preset_used_in_response(self) -> None:
        resp = client.post(
            "/api/v1/generate",
            json={"context": MINIMAL_CONTEXT, "preset_id": "casual_medium_add"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["status"] == "success"
        assert data["prompt_metadata"]["preset_id"] == "casual_medium_add"

    def test_each_preset_resolves(self) -> None:
        for pid in [
            "prof_short_agree",
            "casual_medium_add",
            "supportive_short_encourage",
            "contrarian_medium_challenge",
            "prof_medium_insight",
            "casual_short_react",
            "supportive_medium_story",
            "prof_long_analysis",
        ]:
            preset = get_preset_by_id(pid)
            assert preset is not None
            assert preset.id == pid


# ---------------------------------------------------------------------------
# AC2: Missing/null preset_id → default preset used
# ---------------------------------------------------------------------------


class TestDefaultFallback:
    def test_null_preset_id_uses_default(self) -> None:
        resp = client.post(
            "/api/v1/generate",
            json={"context": MINIMAL_CONTEXT, "preset_id": None},
        )
        assert resp.status_code == 200
        data = resp.json()
        default = get_default_preset()
        assert data["prompt_metadata"]["preset_id"] == default.id

    def test_missing_preset_id_uses_default(self) -> None:
        resp = client.post(
            "/api/v1/generate",
            json={"context": MINIMAL_CONTEXT},
        )
        assert resp.status_code == 200
        data = resp.json()
        default = get_default_preset()
        assert data["prompt_metadata"]["preset_id"] == default.id

    def test_default_fallback_generates_reply(self) -> None:
        resp = client.post(
            "/api/v1/generate",
            json={"context": MINIMAL_CONTEXT},
        )
        assert resp.status_code == 200
        assert len(resp.json()["result"]["reply_text"]) > 0


# ---------------------------------------------------------------------------
# AC3: Invalid preset_id → generation blocked with error
# ---------------------------------------------------------------------------


class TestInvalidPresetBlocked:
    def test_invalid_preset_returns_422(self) -> None:
        resp = client.post(
            "/api/v1/generate",
            json={"context": MINIMAL_CONTEXT, "preset_id": "nonexistent_preset"},
        )
        assert resp.status_code == 422
        assert "Unknown preset_id" in str(resp.json())

    def test_empty_string_preset_returns_422(self) -> None:
        resp = client.post(
            "/api/v1/generate",
            json={"context": MINIMAL_CONTEXT, "preset_id": ""},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC4: Default preset always available and stable
# ---------------------------------------------------------------------------


class TestDefaultStable:
    def test_default_preset_is_always_available(self) -> None:
        default = get_default_preset()
        assert default is not None
        assert default.id
        assert default.is_default is True

    def test_default_preset_lookup_is_stable(self) -> None:
        d1 = get_default_preset()
        d2 = get_default_preset()
        assert d1.id == d2.id
        assert d1 == d2

    def test_default_preset_resolvable_by_id(self) -> None:
        default = get_default_preset()
        looked_up = get_preset_by_id(default.id)
        assert looked_up is not None
        assert looked_up.id == default.id


# ---------------------------------------------------------------------------
# AC5: Different presets reflected in prompt assembly each time
# ---------------------------------------------------------------------------


class TestPromptReflectsPreset:
    def _build_for_preset(self, preset_id: str) -> tuple[str, dict]:
        from backend.app.models.post_context import PostContextInput

        ctx = PostContextInput(post_text="A" * 20, preset_id=preset_id)
        payload, errors = validate_and_build_payload(ctx)
        assert not errors
        assert payload is not None
        preset = get_preset_by_id(preset_id)
        assert preset is not None
        return build_prompt(payload, preset)

    def test_different_presets_produce_different_prompts(self) -> None:
        prompt_agree, meta_agree = self._build_for_preset("prof_short_agree")
        prompt_casual, meta_casual = self._build_for_preset("casual_medium_add")

        assert prompt_agree != prompt_casual
        assert meta_agree["preset_id"] == "prof_short_agree"
        assert meta_casual["preset_id"] == "casual_medium_add"

    def test_prompt_contains_tone_and_intent(self) -> None:
        prompt, _ = self._build_for_preset("contrarian_medium_challenge")
        assert "contrarian" in prompt.lower()
        assert "challenge" in prompt.lower()

    def test_prompt_contains_guidance_bullets(self) -> None:
        prompt, _ = self._build_for_preset("prof_long_analysis")
        assert "structured" in prompt.lower()
        assert "recommendation" in prompt.lower()

    def test_same_preset_produces_identical_prompt(self) -> None:
        p1, _ = self._build_for_preset("casual_short_react")
        p2, _ = self._build_for_preset("casual_short_react")
        assert p1 == p2
