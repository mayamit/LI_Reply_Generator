"""History list view — browse past generated and approved replies (Story 3.3)."""

import logging

import streamlit as st
from backend.app.db.session import SessionLocal
from backend.app.models.presets import get_preset_labels
from backend.app.services.reply_repository import (
    count_records,
    list_records,
)

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Reply History", layout="centered")
st.title("Reply History")

# --- Filters ---
st.subheader("Filters")
col_status, col_author = st.columns(2)

with col_status:
    status_options = ["All", "draft", "approved"]
    selected_status = st.selectbox("Status", options=status_options)

with col_author:
    author_filter = st.text_input(
        "Author name (contains)",
        help="Filter records by author name substring.",
    )

# Resolve filter values
status_filter = None if selected_status == "All" else selected_status
author_filter_val = author_filter.strip() if author_filter else None

# --- Pagination ---
PAGE_SIZE = 20

if "history_page" not in st.session_state:
    st.session_state.history_page = 0

# --- Query ---
db = SessionLocal()
try:
    total = count_records(
        db,
        status=status_filter,
        author_name=author_filter_val,
    )
    records = list_records(
        db,
        status=status_filter,
        author_name=author_filter_val,
        offset=st.session_state.history_page * PAGE_SIZE,
        limit=PAGE_SIZE,
    )
finally:
    db.close()

# --- Empty state (AC1) ---
if total == 0:
    st.info("No saved replies yet.")
    st.stop()

# --- Display records (AC2, AC3) ---
st.caption(f"Showing {len(records)} of {total} records")

preset_labels = get_preset_labels()

# Column headers
header_cols = st.columns([0.5, 2, 2, 1.5, 2, 1])
header_cols[0].markdown("**St.**")
header_cols[1].markdown("**Author**")
header_cols[2].markdown("**Preset**")
header_cols[3].markdown("**Status**")
header_cols[4].markdown("**Date**")
header_cols[5].markdown("**Action**")

for record in records:
    preset_name = preset_labels.get(record.preset_id, record.preset_id)
    status_icon = "✅" if record.status == "approved" else "📝"
    author_display = record.author_name or "—"
    date_display = (
        record.created_date.strftime("%Y-%m-%d %H:%M")
        if record.created_date
        else "—"
    )

    with st.container():
        cols = st.columns([0.5, 2, 2, 1.5, 2, 1])
        cols[0].write(status_icon)
        cols[1].write(f"**{author_display}**")
        cols[2].write(preset_name)
        cols[3].write(record.status)
        cols[4].write(date_display)
        # AC4: Click to open detail view
        if cols[5].button("View", key=f"view_{record.id}"):
            st.session_state.detail_record_id = record.id
            st.switch_page("pages/2_Detail.py")

st.divider()

# --- Pagination controls ---
total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
current_page = st.session_state.history_page

col_prev, col_info, col_next = st.columns([1, 2, 1])

with col_prev:
    if st.button("← Previous", disabled=current_page == 0):
        st.session_state.history_page = current_page - 1
        st.rerun()

with col_info:
    st.write(f"Page {current_page + 1} of {total_pages}")

with col_next:
    if st.button("Next →", disabled=current_page >= total_pages - 1):
        st.session_state.history_page = current_page + 1
        st.rerun()
