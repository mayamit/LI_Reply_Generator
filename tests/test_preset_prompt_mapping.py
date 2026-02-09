"""Tests for preset-to-prompt directive mapping (Story 2.3).

Covers all 5 acceptance criteria:
  AC1: tone, intent, length_bucket → explicit prompt instructions
  AC2: guidance_bullets included verbatim
  AC3: allow_hashtags=false → hashtags explicitly forbidden
  AC4: Identical inputs → byte-for-byte identical prompt
  AC5: New preset works without prompt builder changes
"""

from backend.app.models.post_context import PostContextPayload
from backend.app.models.presets import LengthBucket, ReplyPreset
from backend.app.services.prompt_builder import build_prompt


def _make_payload(**overrides: object) -> PostContextPayload:
    defaults: dict[str, object] = {
        "post_text": "This is a sample LinkedIn post for testing purposes.",
        "preset_id": "prof_short_agree",
        "preset_label": "Professional – Short Agreement",
        "tone": "professional",
        "length_bucket": "short",
        "intent": "agree",
    }
    defaults.update(overrides)
    return PostContextPayload(**defaults)  # type: ignore[arg-type]


def _make_preset(**overrides: object) -> ReplyPreset:
    defaults: dict[str, object] = {
        "id": "test_preset",
        "label": "Test Preset",
        "tone": "professional",
        "length_bucket": LengthBucket.medium,
        "intent": "agree",
    }
    defaults.update(overrides)
    return ReplyPreset(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC1: tone, intent, length_bucket → explicit prompt instructions
# ---------------------------------------------------------------------------


class TestToneIntentLength:
    def test_tone_appears_in_prompt(self) -> None:
        preset = _make_preset(tone="contrarian")
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "Tone: contrarian" in prompt

    def test_intent_appears_in_prompt(self) -> None:
        preset = _make_preset(intent="challenge")
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "Intent: challenge" in prompt

    def test_short_length_guidance(self) -> None:
        preset = _make_preset(length_bucket=LengthBucket.short)
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "1–3 sentences" in prompt

    def test_medium_length_guidance(self) -> None:
        preset = _make_preset(length_bucket=LengthBucket.medium)
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "3–5 sentences" in prompt

    def test_long_length_guidance(self) -> None:
        preset = _make_preset(length_bucket=LengthBucket.long)
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "5–8 sentences" in prompt

    def test_all_three_present_together(self) -> None:
        preset = _make_preset(
            tone="supportive",
            intent="encourage",
            length_bucket=LengthBucket.short,
        )
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "Tone: supportive" in prompt
        assert "Intent: encourage" in prompt
        assert "1–3 sentences" in prompt


# ---------------------------------------------------------------------------
# AC2: guidance_bullets included verbatim
# ---------------------------------------------------------------------------


class TestGuidanceBullets:
    def test_bullets_included_verbatim(self) -> None:
        bullets = [
            "Acknowledge the author's point directly",
            "Add a brief supporting observation",
        ]
        preset = _make_preset(guidance_bullets=bullets)
        prompt, _ = build_prompt(_make_payload(), preset)
        for bullet in bullets:
            assert f"- {bullet}" in prompt

    def test_guidance_header_present(self) -> None:
        preset = _make_preset(guidance_bullets=["Some guidance"])
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "Guidance:" in prompt

    def test_no_guidance_section_when_none(self) -> None:
        preset = _make_preset(guidance_bullets=None)
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "Guidance:" not in prompt

    def test_no_guidance_section_when_empty(self) -> None:
        preset = _make_preset(guidance_bullets=[])
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "Guidance:" not in prompt


# ---------------------------------------------------------------------------
# AC3: allow_hashtags=false → hashtags explicitly forbidden
# ---------------------------------------------------------------------------


class TestHashtagDirective:
    def test_hashtags_forbidden_when_false(self) -> None:
        preset = _make_preset(allow_hashtags=False)
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "Do not include hashtags" in prompt

    def test_no_hashtag_ban_when_true(self) -> None:
        preset = _make_preset(allow_hashtags=True)
        prompt, _ = build_prompt(_make_payload(), preset)
        assert "Do not include hashtags" not in prompt


# ---------------------------------------------------------------------------
# AC4: Identical inputs → byte-for-byte identical prompt
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_identical_inputs_identical_output(self) -> None:
        payload = _make_payload()
        preset = _make_preset(guidance_bullets=["Be concise"])
        p1, m1 = build_prompt(payload, preset)
        p2, m2 = build_prompt(payload, preset)
        assert p1 == p2
        assert m1 == m2

    def test_deterministic_across_many_calls(self) -> None:
        payload = _make_payload()
        preset = _make_preset()
        prompts = [build_prompt(payload, preset)[0] for _ in range(10)]
        assert len(set(prompts)) == 1


# ---------------------------------------------------------------------------
# AC5: New preset works without prompt builder changes
# ---------------------------------------------------------------------------


class TestNewPresetNoBuilderChanges:
    def test_novel_preset_produces_valid_prompt(self) -> None:
        """A completely new preset (not in DEFAULT_PRESETS) works fine."""
        novel = ReplyPreset(
            id="novel_test",
            label="Novel Test Preset",
            tone="whimsical",
            length_bucket=LengthBucket.long,
            intent="entertain",
            guidance_bullets=["Be creative", "Use humor"],
            allow_hashtags=True,
        )
        prompt, meta = build_prompt(_make_payload(), novel)
        assert "Tone: whimsical" in prompt
        assert "Intent: entertain" in prompt
        assert "5–8 sentences" in prompt
        assert "- Be creative" in prompt
        assert "- Use humor" in prompt
        assert "Do not include hashtags" not in prompt
        assert meta["preset_id"] == "novel_test"

    def test_minimal_preset_produces_valid_prompt(self) -> None:
        """Preset with only required fields still produces a prompt."""
        minimal = ReplyPreset(
            id="minimal",
            label="Minimal",
            tone="neutral",
            length_bucket=LengthBucket.short,
            intent="respond",
        )
        prompt, _ = build_prompt(_make_payload(), minimal)
        assert "Tone: neutral" in prompt
        assert "Intent: respond" in prompt
        assert len(prompt) > 0
