"""Streamlit entry point for LI Reply Generator."""

import streamlit as st

st.set_page_config(page_title="LI Reply Generator", layout="centered")

pg = st.navigation(
    [
        st.Page("pages/0_Generate.py", title="Generate Reply", icon="✍️", default=True),
        st.Page("pages/1_History.py", title="Reply History", icon="📋"),
        st.Page("pages/2_Detail.py", title="Reply Detail", icon="📄"),
    ]
)

pg.run()
