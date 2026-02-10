"""Manage Presets page — view, edit, add, and delete reply presets."""

import logging
import re

import httpx
import streamlit as st
from ui_helpers import API_BASE, _safe_error_detail

logger = logging.getLogger(__name__)

st.title("Manage Presets")

TONE_OPTIONS = ["professional", "casual", "supportive", "contrarian"]
LENGTH_OPTIONS = ["short", "medium", "long"]
INTENT_OPTIONS = [
    "agree",
    "add_perspective",
    "encourage",
    "challenge",
    "share_insight",
    "react",
    "share_experience",
    "analyze",
]


def _fetch_presets() -> list[dict] | None:
    """Fetch all presets from the API."""
    try:
        resp = httpx.get(f"{API_BASE}/api/v1/presets", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        st.error(f"Cannot reach API at {API_BASE}. Ensure the API is running.")
        return None


def _bullets_to_text(bullets: list[str] | None) -> str:
    """Convert guidance bullets list to newline-separated text."""
    if not bullets:
        return ""
    return "\n".join(bullets)


def _text_to_bullets(text: str) -> list[str] | None:
    """Convert newline-separated text to guidance bullets list."""
    lines = [line.strip().lstrip("- ").strip() for line in text.strip().splitlines() if line.strip()]
    return lines if lines else None


def _make_preset_id(label: str) -> str:
    """Generate a snake_case ID from a label."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return slug[:100]


# ---------------------------------------------------------------------------
# Add New Preset
# ---------------------------------------------------------------------------
with st.expander("Add New Preset", icon="➕"):
    with st.form("add_preset_form"):
        new_label = st.text_input("Label *", placeholder="e.g. Thoughtful – Medium Question")
        new_description = st.text_area(
            "Description",
            placeholder="Describe what this preset does...",
            height=80,
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            new_tone = st.selectbox("Tone *", TONE_OPTIONS, key="new_tone")
        with col2:
            new_length = st.selectbox("Length *", LENGTH_OPTIONS, key="new_length")
        with col3:
            new_intent = st.text_input("Intent *", placeholder="e.g. ask_question", key="new_intent")

        new_bullets = st.text_area(
            "Guidance Bullets (one per line)",
            placeholder="Ask a thoughtful follow-up question\nShow genuine curiosity about the topic",
            height=100,
            key="new_bullets",
        )
        new_hashtags = st.checkbox("Allow hashtags", key="new_hashtags")
        new_default = st.checkbox("Set as default", key="new_default")

        add_submitted = st.form_submit_button("Add Preset", type="primary")

    if add_submitted:
        if not new_label or not new_intent:
            st.error("Label and Intent are required.")
        else:
            preset_id = _make_preset_id(new_label)
            preset_data = {
                "id": preset_id,
                "label": new_label,
                "tone": new_tone,
                "length_bucket": new_length,
                "intent": new_intent.strip(),
                "description": new_description or None,
                "guidance_bullets": _text_to_bullets(new_bullets),
                "allow_hashtags": new_hashtags,
                "is_default": new_default,
            }
            try:
                resp = httpx.post(
                    f"{API_BASE}/api/v1/presets",
                    json=preset_data,
                    timeout=10,
                )
                if resp.status_code == 201:
                    st.success(f"Preset '{new_label}' created!")
                    st.rerun()
                else:
                    st.error(f"Failed to create preset: {_safe_error_detail(resp)}")
            except Exception:
                st.error(f"Cannot reach API at {API_BASE}.")

st.divider()

# ---------------------------------------------------------------------------
# List & Edit Existing Presets
# ---------------------------------------------------------------------------
presets = _fetch_presets()
if presets is None:
    st.stop()

if not presets:
    st.info("No presets found. Add one above!")
    st.stop()

st.subheader(f"Existing Presets ({len(presets)})")

for preset in presets:
    pid = preset["id"]
    label = preset["label"]
    is_default = preset.get("is_default", False)
    badge = " (Default)" if is_default else ""

    with st.expander(f"{label}{badge}", icon="⚙️"):
        # Show the prompt details
        st.caption(f"ID: `{pid}`")

        with st.form(f"edit_{pid}"):
            edit_label = st.text_input("Label", value=label, key=f"label_{pid}")
            edit_description = st.text_area(
                "Description",
                value=preset.get("description") or "",
                height=80,
                key=f"desc_{pid}",
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                tone_idx = TONE_OPTIONS.index(preset["tone"]) if preset["tone"] in TONE_OPTIONS else 0
                edit_tone = st.selectbox("Tone", TONE_OPTIONS, index=tone_idx, key=f"tone_{pid}")
            with col2:
                len_idx = LENGTH_OPTIONS.index(preset["length_bucket"]) if preset["length_bucket"] in LENGTH_OPTIONS else 0
                edit_length = st.selectbox("Length", LENGTH_OPTIONS, index=len_idx, key=f"len_{pid}")
            with col3:
                intent_val = preset.get("intent", "")
                if intent_val in INTENT_OPTIONS:
                    intent_idx = INTENT_OPTIONS.index(intent_val)
                    edit_intent = st.selectbox("Intent", INTENT_OPTIONS, index=intent_idx, key=f"intent_{pid}")
                else:
                    edit_intent = st.text_input("Intent", value=intent_val, key=f"intent_{pid}")

            edit_bullets = st.text_area(
                "Guidance Bullets (one per line — these feed into the LLM prompt)",
                value=_bullets_to_text(preset.get("guidance_bullets")),
                height=120,
                key=f"bullets_{pid}",
            )

            edit_hashtags = st.checkbox(
                "Allow hashtags",
                value=preset.get("allow_hashtags", False),
                key=f"hash_{pid}",
            )
            edit_default = st.checkbox(
                "Set as default",
                value=is_default,
                key=f"default_{pid}",
            )

            col_save, col_delete = st.columns([1, 1])
            with col_save:
                save_clicked = st.form_submit_button("Save Changes", type="primary")
            with col_delete:
                delete_clicked = st.form_submit_button("Delete Preset")

        if save_clicked:
            updated = {
                "id": pid,
                "label": edit_label,
                "tone": edit_tone,
                "length_bucket": edit_length,
                "intent": edit_intent,
                "description": edit_description or None,
                "guidance_bullets": _text_to_bullets(edit_bullets),
                "allow_hashtags": edit_hashtags,
                "is_default": edit_default,
            }
            try:
                resp = httpx.put(
                    f"{API_BASE}/api/v1/presets/{pid}",
                    json=updated,
                    timeout=10,
                )
                if resp.status_code == 200:
                    st.success(f"Preset '{edit_label}' updated!")
                    st.rerun()
                else:
                    st.error(f"Failed to update: {_safe_error_detail(resp)}")
            except Exception:
                st.error(f"Cannot reach API at {API_BASE}.")

        if delete_clicked:
            if is_default:
                st.error("Cannot delete the default preset. Set another preset as default first.")
            else:
                try:
                    resp = httpx.delete(
                        f"{API_BASE}/api/v1/presets/{pid}",
                        timeout=10,
                    )
                    if resp.status_code == 204:
                        st.success(f"Preset '{label}' deleted.")
                        st.rerun()
                    else:
                        st.error(f"Failed to delete: {_safe_error_detail(resp)}")
                except Exception:
                    st.error(f"Cannot reach API at {API_BASE}.")
