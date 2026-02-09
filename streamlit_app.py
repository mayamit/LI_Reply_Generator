"""Minimal Streamlit UI scaffold for LI Reply Generator."""

import streamlit as st

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

# --- Placeholder sections (EPIC 1 business logic will go here) ---
st.subheader("Original Post")
post_text = st.text_area("Paste the LinkedIn post you want to reply to", height=150)

st.subheader("Reply Preferences")
tone = st.selectbox("Tone", ["Professional", "Casual", "Supportive", "Contrarian"])
length = st.slider("Approximate length (words)", min_value=20, max_value=300, value=80)

st.subheader("Generated Reply")
st.info("Reply generation is not yet implemented. This is a placeholder for EPIC 1.")
