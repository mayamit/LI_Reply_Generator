"""Detail view placeholder for a single reply record (Story 3.4)."""

import streamlit as st
from backend.app.db.session import SessionLocal
from backend.app.services.reply_repository import (
    RecordNotFoundError,
    get_by_id,
)

st.set_page_config(page_title="Reply Detail", layout="centered")
st.title("Reply Detail")

record_id = st.session_state.get("detail_record_id")

if record_id is None:
    st.warning("No record selected. Go to History to choose a record.")
    st.stop()

db = SessionLocal()
try:
    record = get_by_id(db, record_id)
except RecordNotFoundError:
    st.error(f"Record #{record_id} not found.")
    db.close()
    st.stop()
finally:
    db.close()

st.subheader(f"Record #{record.id}")
st.write(f"**Status:** {record.status}")
st.write(f"**Author:** {record.author_name or '—'}")
st.write(f"**Preset:** {record.preset_id}")
st.write(f"**Created:** {record.created_date}")

if record.generated_reply:
    st.subheader("Generated Reply")
    st.text_area(
        "Generated text",
        value=record.generated_reply,
        disabled=True,
        height=150,
    )

if record.final_reply:
    st.subheader("Approved Reply")
    st.text_area(
        "Final text",
        value=record.final_reply,
        disabled=True,
        height=150,
    )

if record.post_text:
    with st.expander("Original Post"):
        st.write(record.post_text)

if st.button("← Back to History"):
    st.switch_page("pages/1_History.py")
