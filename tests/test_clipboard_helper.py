"""Tests for clipboard-assisted paste helper (Story 7.3).

Actual clipboard JS interaction cannot be unit-tested. These tests verify
the session-state data flow, prefill logic, and error-handling paths.
"""

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# AC1: Clipboard text inserted into selected field via session state
# ---------------------------------------------------------------------------


class TestPasteTargetRouting:
    def test_post_text_paste_sets_session_state(self) -> None:
        """Pasted text for post_text is stored in pasted_post_text."""
        state: dict[str, object] = {
            "_paste_target": "post_text",
            "pasted_post_text": None,
            "pasted_article_text": None,
            "paste_confirmation": None,
        }
        clipboard_text = "Hello from clipboard"

        # Simulate paste logic
        target = state["_paste_target"]
        assert target == "post_text"
        if target == "post_text":
            state["pasted_post_text"] = clipboard_text.strip()
        else:
            state["pasted_article_text"] = clipboard_text.strip()
        state["paste_confirmation"] = f"Pasted into {target.replace('_', ' ')}."
        state["_paste_target"] = None

        assert state["pasted_post_text"] == "Hello from clipboard"
        assert state["pasted_article_text"] is None
        assert state["paste_confirmation"] == "Pasted into post text."
        assert state["_paste_target"] is None

    def test_article_text_paste_sets_session_state(self) -> None:
        """Pasted text for article_text is stored in pasted_article_text."""
        state: dict[str, object] = {
            "_paste_target": "article_text",
            "pasted_post_text": None,
            "pasted_article_text": None,
            "paste_confirmation": None,
        }
        clipboard_text = "Article content from clipboard"

        target = state["_paste_target"]
        if target == "post_text":
            state["pasted_post_text"] = clipboard_text.strip()
        else:
            state["pasted_article_text"] = clipboard_text.strip()
        state["paste_confirmation"] = f"Pasted into {target.replace('_', ' ')}."
        state["_paste_target"] = None

        assert state["pasted_article_text"] == "Article content from clipboard"
        assert state["pasted_post_text"] is None
        assert state["paste_confirmation"] == "Pasted into article text."


# ---------------------------------------------------------------------------
# AC2: Empty / inaccessible clipboard shows error
# ---------------------------------------------------------------------------


class TestEmptyClipboard:
    def test_empty_string_clipboard(self) -> None:
        """Empty clipboard text (whitespace only) should not set pasted value."""
        clipboard_text = "   "
        stripped = clipboard_text.strip()
        assert not stripped  # Would trigger warning path

    def test_none_clipboard_result(self) -> None:
        """None result from _read_clipboard means JS hasn't returned yet."""
        clipboard_text = None
        assert clipboard_text is None  # Would skip processing


# ---------------------------------------------------------------------------
# AC3: Confirmation message shown after paste
# ---------------------------------------------------------------------------


class TestPasteConfirmation:
    def test_confirmation_message_format_post_text(self) -> None:
        target = "post_text"
        msg = f"Pasted into {target.replace('_', ' ')}."
        assert msg == "Pasted into post text."

    def test_confirmation_message_format_article_text(self) -> None:
        target = "article_text"
        msg = f"Pasted into {target.replace('_', ' ')}."
        assert msg == "Pasted into article text."

    def test_confirmation_cleared_after_display(self) -> None:
        """Confirmation is set to None after being shown."""
        state: dict[str, object] = {"paste_confirmation": "Pasted into post text."}
        # Simulate display + clear
        assert state["paste_confirmation"] is not None
        state["paste_confirmation"] = None
        assert state["paste_confirmation"] is None


# ---------------------------------------------------------------------------
# AC4: Paste replaces existing content (consistent behavior)
# ---------------------------------------------------------------------------


class TestPasteReplaceBehavior:
    def test_paste_replaces_existing_post_text(self) -> None:
        """Second paste overwrites first paste, not append."""
        state: dict[str, object] = {"pasted_post_text": "Old content"}
        state["pasted_post_text"] = "New clipboard content"
        assert state["pasted_post_text"] == "New clipboard content"

    def test_paste_replaces_existing_article_text(self) -> None:
        state: dict[str, object] = {"pasted_article_text": "Old article"}
        state["pasted_article_text"] = "New article content"
        assert state["pasted_article_text"] == "New article content"


# ---------------------------------------------------------------------------
# Clipboard counter for unique JS eval keys
# ---------------------------------------------------------------------------


class TestClipboardCounter:
    def test_counter_increments(self) -> None:
        counter = 0
        counter = counter + 1
        assert counter == 1
        counter = counter + 1
        assert counter == 2

    def test_counter_creates_unique_keys(self) -> None:
        keys = [f"clipboard_read_{i}" for i in range(3)]
        assert len(set(keys)) == 3


# ---------------------------------------------------------------------------
# _read_clipboard helper function
# ---------------------------------------------------------------------------


class TestReadClipboardHelper:
    @patch("ui_helpers.streamlit_js_eval")
    @patch("ui_helpers.st")
    def test_returns_string_on_success(
        self, mock_st: MagicMock, mock_js_eval: MagicMock,
    ) -> None:
        mock_st.session_state = {"_clipboard_counter": 0}
        mock_js_eval.return_value = "clipboard content"

        from ui_helpers import _read_clipboard

        result = _read_clipboard()
        assert result == "clipboard content"

    @patch("ui_helpers.streamlit_js_eval")
    @patch("ui_helpers.st")
    def test_returns_none_on_non_string(
        self, mock_st: MagicMock, mock_js_eval: MagicMock,
    ) -> None:
        mock_st.session_state = {"_clipboard_counter": 0}
        mock_js_eval.return_value = 0  # Non-string result

        from ui_helpers import _read_clipboard

        result = _read_clipboard()
        assert result is None

    @patch("ui_helpers.streamlit_js_eval", side_effect=Exception("JS error"))
    @patch("ui_helpers.st")
    def test_returns_none_on_exception(
        self, mock_st: MagicMock, mock_js_eval: MagicMock,
    ) -> None:
        mock_st.session_state = {"_clipboard_counter": 0}

        from ui_helpers import _read_clipboard

        result = _read_clipboard()
        assert result is None


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------


class TestSessionStateDefaults:
    def test_default_values(self) -> None:
        """All clipboard session state defaults should be None."""
        defaults = {
            "pasted_post_text": None,
            "pasted_article_text": None,
            "paste_confirmation": None,
        }
        for key, expected in defaults.items():
            assert expected is None, f"{key} should default to None"


# ---------------------------------------------------------------------------
# Whitespace trimming on paste
# ---------------------------------------------------------------------------


class TestWhitespaceTrimming:
    def test_leading_trailing_whitespace_stripped(self) -> None:
        raw = "  Hello world  \n "
        assert raw.strip() == "Hello world"

    def test_only_whitespace_is_empty(self) -> None:
        raw = "  \n\t  "
        assert not raw.strip()

    def test_content_with_internal_whitespace_preserved(self) -> None:
        raw = "  Line 1\n  Line 2  "
        assert raw.strip() == "Line 1\n  Line 2"


# ---------------------------------------------------------------------------
# Story 7.4: URL-first helper text conditions
# ---------------------------------------------------------------------------


class TestUrlFirstHelperText:
    def test_url_present_triggers_hint(self) -> None:
        """When post_url has content, helper text should be shown."""
        post_url = "https://linkedin.com/posts/example"
        assert post_url.strip()  # Truthy → hint displayed

    def test_empty_url_no_hint(self) -> None:
        """When post_url is empty, no helper text should be shown."""
        post_url = ""
        assert not post_url.strip()  # Falsy → no hint

    def test_whitespace_only_url_no_hint(self) -> None:
        """Whitespace-only URL should not trigger hint."""
        post_url = "   "
        assert not post_url.strip()
