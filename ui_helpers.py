"""Shared UI helper functions for the Streamlit frontend."""

import html
import logging

import httpx
import streamlit as st
import streamlit.components.v1 as components
from backend.app.core.settings import settings
from streamlit_js_eval import streamlit_js_eval

logger = logging.getLogger(__name__)

API_BASE = f"http://{settings.api_host}:{settings.api_port}"


def _copy_to_clipboard(text: str) -> None:
    """Inject JS to copy *text* to the clipboard with visual feedback."""
    escaped = html.escape(text).replace("`", "\\`").replace("$", "\\$")
    components.html(
        f"""
        <script>
        const text = `{escaped}`;
        navigator.clipboard.writeText(text).then(function() {{
            document.getElementById('cb-msg').innerText = 'Copied to clipboard!';
            document.getElementById('cb-msg').style.color = '#28a745';
        }}).catch(function() {{
            document.getElementById('cb-msg').innerText =
                'Clipboard not available — please select the text and copy manually.';
            document.getElementById('cb-msg').style.color = '#dc3545';
        }});
        </script>
        <p id="cb-msg" style="font-size:14px; margin:0;"></p>
        """,
        height=30,
    )


def _safe_error_detail(resp: httpx.Response) -> str:
    """Extract a user-friendly error message from an API response.

    Never exposes raw stack traces or secrets.
    """
    try:
        body = resp.json()
        detail = body.get("detail", "")
        if isinstance(detail, list):
            return "; ".join(str(d) for d in detail)
        return str(detail)
    except Exception:
        return f"Unexpected error (HTTP {resp.status_code}). Please try again."


def _read_clipboard() -> str | None:
    """Read text from the browser clipboard via JS. Returns None on failure."""
    try:
        result = streamlit_js_eval(
            js_expressions="navigator.clipboard.readText()",
            key="clipboard_read_"
            + str(st.session_state.get("_clipboard_counter", 0)),
        )
        return result if isinstance(result, str) else None
    except Exception:
        return None


def _has_unsaved_draft() -> bool:
    """Return True if there is a generated reply that has not been approved."""
    return bool(st.session_state.reply_text) and not st.session_state.approved


def _reset_session() -> None:
    """Clear all generation-related session state for a fresh start."""
    st.session_state.reply_text = ""
    st.session_state.record_id = None
    st.session_state.approved = False
    st.session_state.generation_meta = None
    st.session_state.generating = False
    st.session_state.approving = False
    st.session_state.last_error = None
    st.session_state.last_error_retryable = False
    st.session_state.confirm_new_reply = False
    st.session_state.pasted_post_text = None
    st.session_state.pasted_article_text = None
    st.session_state.paste_confirmation = None
