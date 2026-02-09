"""Detail view for a single reply record (Story 3.4)."""

import streamlit as st
from backend.app.db.session import SessionLocal
from backend.app.models.presets import get_preset_labels
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

# --- Header ---
preset_labels = get_preset_labels()
preset_display = preset_labels.get(record.preset_id, record.preset_id)
status_icon = "✅" if record.status == "approved" else "📝"
st.subheader(f"{status_icon} Record #{record.id}")

# --- Status & Timestamps ---
st.markdown("### Status & Timestamps")
col_s1, col_s2, col_s3 = st.columns(3)
col_s1.metric("Status", record.status.capitalize())
col_s2.metric(
    "Created",
    record.created_date.strftime("%Y-%m-%d %H:%M") if record.created_date else "—",
)
if record.status == "approved" and record.approved_at:
    col_s3.metric("Approved", record.approved_at.strftime("%Y-%m-%d %H:%M"))
else:
    col_s3.metric("Approved", "Not approved")

if record.generated_at:
    st.caption(f"Generated at: {record.generated_at.strftime('%Y-%m-%d %H:%M')}")

# --- Author & Links ---
st.markdown("### Author & Links")

author_display = record.author_name or "—"
if record.author_profile_url:
    # AC3: URL opens externally
    st.markdown(
        f"**Author:** [{author_display}]({record.author_profile_url})"
    )
else:
    st.write(f"**Author:** {author_display}")

if record.post_url:
    st.markdown(f"**Post URL:** [{record.post_url}]({record.post_url})")
else:
    st.write("**Post URL:** —")

# --- Preset ---
st.markdown("### Preset")
st.write(f"**Preset:** {preset_display} (`{record.preset_id}`)")

# --- Original Post ---
st.markdown("### Original Post")
st.text_area(
    "Post text",
    value=record.post_text or "",
    disabled=True,
    height=150,
    label_visibility="collapsed",
)

if record.article_text:
    with st.expander("Linked Article Text"):
        st.write(record.article_text)

if record.image_ref:
    st.write(f"**Image reference:** {record.image_ref}")

# --- Generated Reply ---
st.markdown("### Generated Reply")
if record.generated_reply:
    st.text_area(
        "Generated reply text",
        value=record.generated_reply,
        disabled=True,
        height=150,
        label_visibility="collapsed",
    )
else:
    st.info("No generated reply recorded.")

# --- Approved Reply (AC2: show "Not approved" for drafts) ---
st.markdown("### Approved Reply")
if record.status == "approved" and record.final_reply:
    st.text_area(
        "Final approved reply text",
        value=record.final_reply,
        disabled=True,
        height=150,
        label_visibility="collapsed",
    )
else:
    st.info("Not approved")

# --- LLM Metadata ---
if record.llm_model_identifier or record.llm_request_id:
    with st.expander("LLM Metadata"):
        if record.llm_model_identifier:
            st.write(f"**Model:** {record.llm_model_identifier}")
        if record.llm_request_id:
            st.write(f"**Request ID:** {record.llm_request_id}")

# --- Navigation ---
st.divider()
if st.button("← Back to History"):
    st.switch_page("pages/1_History.py")
