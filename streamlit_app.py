"""Streamlit UI for LI Reply Generator — Story 1.1: Post Context Capture."""

import streamlit as st
from pydantic import ValidationError

from backend.app.models.post_context import PostContextInput
from backend.app.models.presets import get_preset_labels
from backend.app.services.validation import validate_and_build_payload

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="LI Reply Generator", layout="centered")
st.title("LinkedIn Reply Generator")

# --- API connectivity check ---
st.subheader("API Status")
if st.button("Check API health"):
    import httpx

    try:
        resp = httpx.get(f"{API_BASE}/health", timeout=5)
        resp.raise_for_status()
        st.success(f"API is reachable: {resp.json()}")
    except Exception as exc:
        st.error(f"Cannot reach API: {exc}")

st.divider()

# --- Post Context Input Form ---
st.subheader("Original Post")

preset_labels = get_preset_labels()
label_to_id = {label: pid for pid, label in preset_labels.items()}

with st.form("post_context_form"):
    post_text = st.text_area(
        "Paste the LinkedIn post you want to reply to",
        height=150,
        help="Required — at least 10 characters.",
    )

    st.subheader("Reply Preset")
    selected_label = st.selectbox("Choose a reply preset", options=list(label_to_id.keys()))

    st.subheader("Optional Context")
    author_name = st.text_input("Author name")
    author_profile_url = st.text_input("Author profile URL")
    post_url = st.text_input("Post URL")
    article_text = st.text_area("Linked article text (if any)", height=100)
    image_ref = st.text_input("Image reference / alt text")

    submitted = st.form_submit_button("Validate & Preview")

if submitted:
    preset_id = label_to_id[selected_label]

    # Build raw input dict, omitting empty optional fields
    raw: dict[str, str] = {"post_text": post_text, "preset_id": preset_id}
    for key, val in [
        ("author_name", author_name),
        ("author_profile_url", author_profile_url),
        ("post_url", post_url),
        ("article_text", article_text),
        ("image_ref", image_ref),
    ]:
        if val:
            raw[key] = val

    # --- Pydantic field validation ---
    try:
        ctx = PostContextInput(**raw)
    except ValidationError as exc:
        for err in exc.errors():
            field = " -> ".join(str(loc) for loc in err["loc"])
            st.error(f"**{field}**: {err['msg']}")
        st.stop()

    # --- Business validation (preset lookup, URL checks) ---
    payload, errors = validate_and_build_payload(ctx)
    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    assert payload is not None
    for w in payload.validation_warnings:
        st.warning(w)

    st.success("Input validated successfully!")
    with st.expander("Validated Payload", expanded=True):
        st.json(payload.model_dump())

st.divider()

# --- Placeholder for future stories ---
st.subheader("Generated Reply")
st.info("Reply generation is not yet implemented. This is a placeholder for Story 1.3.")
