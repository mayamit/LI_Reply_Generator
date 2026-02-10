"""Streamlit UI for LI Reply Generator."""

import html
import logging

import httpx
import streamlit as st
import streamlit.components.v1 as components
from backend.app.core.settings import settings
from backend.app.models.post_context import PostContextInput
from backend.app.models.presets import get_preset_description, get_preset_labels
from backend.app.services.validation import validate_and_build_payload
from pydantic import ValidationError
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


st.set_page_config(page_title="LI Reply Generator", layout="centered")
st.title("LinkedIn Reply Generator")

if not settings.is_llm_configured:
    st.warning(
        "LLM is not configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
        "in your environment or .env file to enable reply generation."
    )

# --- Session state defaults ---
if "reply_text" not in st.session_state:
    st.session_state.reply_text = ""
if "record_id" not in st.session_state:
    st.session_state.record_id = None
if "approved" not in st.session_state:
    st.session_state.approved = False
if "generation_meta" not in st.session_state:
    st.session_state.generation_meta = None
if "generating" not in st.session_state:
    st.session_state.generating = False
if "approving" not in st.session_state:
    st.session_state.approving = False
if "last_error" not in st.session_state:
    st.session_state.last_error = None
if "last_error_retryable" not in st.session_state:
    st.session_state.last_error_retryable = False
if "confirm_new_reply" not in st.session_state:
    st.session_state.confirm_new_reply = False
if "pasted_post_text" not in st.session_state:
    st.session_state.pasted_post_text = None
if "pasted_article_text" not in st.session_state:
    st.session_state.pasted_article_text = None
if "paste_confirmation" not in st.session_state:
    st.session_state.paste_confirmation = None


def _has_unsaved_draft() -> bool:
    """Return True if there is a generated reply that has not been approved."""
    return bool(st.session_state.reply_text) and not st.session_state.approved


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


# --- New Reply button ---
if st.session_state.reply_text:
    if st.button("New Reply"):
        if _has_unsaved_draft():
            st.session_state.confirm_new_reply = True
        else:
            _reset_session()
            st.rerun()

if st.session_state.confirm_new_reply:
    st.warning(
        "You have an unsaved draft reply that has not been approved. "
        "Starting a new reply will discard it."
    )
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Discard draft and start new", type="primary"):
            _reset_session()
            st.rerun()
    with col_cancel:
        if st.button("Keep editing"):
            st.session_state.confirm_new_reply = False
            st.rerun()

# --- API connectivity check ---
st.subheader("API Status")
if st.button("Check API health"):
    try:
        resp = httpx.get(f"{API_BASE}/health", timeout=5)
        resp.raise_for_status()
        st.success(f"API is reachable: {resp.json()}")
    except Exception:
        st.error(
            "Cannot reach API. Ensure the API is running "
            f"at {API_BASE} (run `make run-api`)."
        )

st.divider()

# --- Post Context Input Form ---
st.subheader("Original Post")

# --- Clipboard paste helpers (outside form — forms don't support callbacks) ---
paste_col1, paste_col2 = st.columns(2)
with paste_col1:
    if st.button("📋 Paste into Post Text"):
        st.session_state._clipboard_counter = (
            st.session_state.get("_clipboard_counter", 0) + 1
        )
        st.session_state._paste_target = "post_text"
with paste_col2:
    if st.button("📋 Paste into Article Text"):
        st.session_state._clipboard_counter = (
            st.session_state.get("_clipboard_counter", 0) + 1
        )
        st.session_state._paste_target = "article_text"

if st.session_state.get("_paste_target"):
    clipboard_text = _read_clipboard()
    if clipboard_text and clipboard_text.strip():
        target = st.session_state._paste_target
        if target == "post_text":
            st.session_state.pasted_post_text = clipboard_text.strip()
        else:
            st.session_state.pasted_article_text = clipboard_text.strip()
        st.session_state.paste_confirmation = (
            f"Pasted into {target.replace('_', ' ')}."
        )
        st.session_state._paste_target = None
        st.rerun()
    elif clipboard_text is not None:
        st.warning("Clipboard is empty. Copy some text first.")
        st.session_state._paste_target = None

if st.session_state.paste_confirmation:
    st.success(st.session_state.paste_confirmation)
    st.session_state.paste_confirmation = None

preset_labels = get_preset_labels()
label_to_id = {label: pid for pid, label in preset_labels.items()}

# Preset selector outside the form so description updates on change
st.subheader("Reply Preset")
selected_label = st.selectbox("Choose a reply preset", options=list(label_to_id.keys()))
st.caption(get_preset_description(label_to_id[selected_label]))

with st.form("post_context_form"):
    post_text = st.text_area(
        "Paste the LinkedIn post you want to reply to",
        value=st.session_state.get("pasted_post_text") or "",
        height=150,
        help="Required — at least 10 characters.",
    )

    st.subheader("Optional Context")
    author_name = st.text_input(
        "Author name",
        help="Name of the post author (max 200 characters).",
    )
    author_profile_url = st.text_input(
        "Author profile URL",
        help="LinkedIn profile URL of the post author.",
    )
    post_url = st.text_input(
        "Post URL",
        help="Direct link to the LinkedIn post.",
    )
    if post_url.strip():
        st.link_button("Open Post ↗", post_url.strip())
    article_text = st.text_area(
        "Linked article text (if any)",
        value=st.session_state.get("pasted_article_text") or "",
        height=100,
        help="Paste the article body if the post links to one (max 50,000 characters).",
    )
    image_ref = st.text_input(
        "Image reference / alt text",
        help="Describe any image attached to the post (max 2,000 characters).",
    )

    st.subheader("Engagement Signals")
    eng_col1, eng_col2 = st.columns(2)
    with eng_col1:
        follower_count = st.number_input(
            "Follower count",
            min_value=0,
            value=None,
            step=1,
            help="Number of followers the post author has.",
            placeholder="e.g. 5000",
        )
        like_count = st.number_input(
            "Like count",
            min_value=0,
            value=None,
            step=1,
            help="Number of likes on the post.",
            placeholder="e.g. 120",
        )
    with eng_col2:
        comment_count = st.number_input(
            "Comment count",
            min_value=0,
            value=None,
            step=1,
            help="Number of comments on the post.",
            placeholder="e.g. 30",
        )
        repost_count = st.number_input(
            "Repost count",
            min_value=0,
            value=None,
            step=1,
            help="Number of reposts/shares of the post.",
            placeholder="e.g. 15",
        )

    # AC1: Disable submit while generation is in progress
    submitted = st.form_submit_button(
        "Validate & Generate Reply",
        type="primary",
        disabled=st.session_state.generating,
    )

if submitted:
    # Reset state for new generation
    st.session_state.reply_text = ""
    st.session_state.record_id = None
    st.session_state.approved = False
    st.session_state.generation_meta = None
    st.session_state.last_error = None
    st.session_state.last_error_retryable = False
    st.session_state.generating = True

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
    for key, val in [
        ("follower_count", follower_count),
        ("like_count", like_count),
        ("comment_count", comment_count),
        ("repost_count", repost_count),
    ]:
        if val is not None:
            raw[key] = val

    # --- Pydantic field validation (AC8: inputs preserved on error) ---
    try:
        ctx = PostContextInput(**raw)
    except ValidationError as exc:
        _FIELD_HINTS: dict[str, str] = {
            "post_text": "Paste the LinkedIn post text (at least 10 characters).",
            "article_text": "Shorten the article text or remove unnecessary sections.",
            "author_profile_url": "Enter a shorter or valid URL.",
            "post_url": "Enter a shorter or valid URL.",
            "image_ref": "Keep the image reference under 2,000 characters.",
            "author_name": "Keep the author name under 200 characters.",
        }
        for err in exc.errors():
            field = " -> ".join(str(loc) for loc in err["loc"])
            hint = _FIELD_HINTS.get(field, "")
            msg = f"**{field}**: {err['msg']}"
            if hint:
                msg += f" — {hint}"
            st.error(msg)
        st.session_state.generating = False
        st.stop()

    # --- Business validation (preset lookup, URL checks) ---
    payload, errors = validate_and_build_payload(ctx)
    if errors:
        for e in errors:
            st.error(e)
        st.session_state.generating = False
        st.stop()

    assert payload is not None
    for w in payload.validation_warnings:
        st.warning(w)

    st.success("Input validated successfully!")
    with st.expander("Validated Payload"):
        st.json(payload.model_dump())

    # --- Call generate endpoint (AC1: spinner during generation) ---
    with st.spinner("Generating reply..."):
        try:
            resp = httpx.post(
                f"{API_BASE}/api/v1/generate",
                json={"context": ctx.model_dump(), "preset_id": preset_id},
                timeout=60,
            )
        except Exception:
            st.session_state.last_error = (
                "Could not reach API. Ensure the API is running "
                f"at {API_BASE} (run `make run-api`)."
            )
            st.session_state.last_error_retryable = True
            st.session_state.generating = False
            st.error(st.session_state.last_error)
            st.info("Your inputs are preserved. Fix the issue and try again.")
            st.stop()

    st.session_state.generating = False

    if resp.status_code == 503:
        st.warning(
            "LLM not configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "in your .env file to enable reply generation."
        )
        st.stop()

    # AC7: User-friendly error messages, no stack traces
    if resp.status_code != 200:
        detail = _safe_error_detail(resp)
        st.session_state.last_error = f"Generation failed: {detail}"
        st.session_state.last_error_retryable = resp.status_code >= 500
        st.error(st.session_state.last_error)
        if st.session_state.last_error_retryable:
            st.info("This error may be temporary. Your inputs are preserved — try again.")
        st.stop()

    data = resp.json()
    result = data["result"]

    if result["status"] == "success":
        # AC2: Success confirmation after generation
        st.session_state.reply_text = result["reply_text"]
        st.session_state.record_id = data.get("record_id")
        st.session_state.generation_meta = {
            "model_id": result.get("model_id", "N/A"),
            "latency_ms": result.get("latency_ms", "N/A"),
        }
        st.session_state.last_error = None
        st.success("Reply generated successfully!")
        if data.get("record_id") is None:
            st.warning(
                "Draft could not be saved to database. "
                "You can still copy the reply text."
            )
    else:
        # AC3: Retryable errors offer retry path
        msg = result.get("user_message", "Unknown error")
        is_retryable = result.get("retryable", False)
        st.session_state.last_error = msg
        st.session_state.last_error_retryable = is_retryable
        if is_retryable:
            st.warning(f"{msg}")
            st.info("This error is retryable. Your inputs are preserved — try again.")
        else:
            st.error(msg)

    if data.get("prompt_metadata"):
        with st.expander("Prompt Metadata"):
            st.json(data["prompt_metadata"])

# --- Editable Reply + Approve & Save ---
st.divider()
st.subheader("Generated Reply")

if st.session_state.reply_text:
    is_approved = st.session_state.approved

    # Editable multiline field pre-filled with generated text
    # Editing disabled after approval (AC5)
    edited_reply = st.text_area(
        "Edit your reply before approving",
        value=st.session_state.reply_text,
        height=200,
        disabled=is_approved,
        key="reply_editor",
    )

    if st.session_state.generation_meta:
        meta = st.session_state.generation_meta
        st.caption(f"Model: {meta['model_id']} | Latency: {meta['latency_ms']}ms")

    # --- Action buttons ---
    if is_approved:
        st.success("Reply approved and saved!")

    col_approve, col_copy = st.columns([1, 1])

    with col_copy:
        # AC6: Copy confirmation
        copy_clicked = st.button(
            "Copy to Clipboard",
            disabled=not edited_reply or not edited_reply.strip(),
        )
        if copy_clicked:
            if edited_reply and edited_reply.strip():
                _copy_to_clipboard(edited_reply)
                logger.info("reply_copied")

    if not is_approved:
        with col_approve:
            # AC4: Disable approve while in progress
            approve_clicked = st.button(
                "Approve & Save",
                type="primary",
                disabled=st.session_state.approving,
            )
            if approve_clicked:
                if not edited_reply or not edited_reply.strip():
                    st.error(
                        "Reply text cannot be empty. "
                        "Please edit before approving."
                    )
                elif st.session_state.record_id is None:
                    st.error("No draft record available. Generate a reply first.")
                else:
                    st.session_state.approving = True
                    # AC4: Spinner during approval
                    with st.spinner("Saving approval..."):
                        try:
                            resp = httpx.post(
                                f"{API_BASE}/api/v1/approve",
                                json={
                                    "record_id": st.session_state.record_id,
                                    "final_reply": edited_reply,
                                },
                                timeout=10,
                            )
                        except Exception:
                            st.session_state.approving = False
                            st.error(
                                "Could not reach API. "
                                "Your edits are preserved — try again."
                            )
                            st.stop()

                    st.session_state.approving = False

                    if resp.status_code == 200:
                        # AC5: Success confirmation + locked state
                        st.session_state.approved = True
                        st.session_state.reply_text = edited_reply
                        st.success("Reply approved and saved!")
                        st.rerun()
                    else:
                        # AC7: User-friendly error
                        detail = _safe_error_detail(resp)
                        st.error(
                            f"Approval failed: {detail}. "
                            "Your edits are preserved — try again."
                        )
else:
    st.info("Submit the form above to generate a reply.")
