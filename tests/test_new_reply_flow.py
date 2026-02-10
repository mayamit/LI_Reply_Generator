"""Tests for Story 5.5: Safe Reset/Clear and New Reply flow.

Covers acceptance criteria:
  AC1: Unapproved edited reply → confirmation before clearing
  AC2: Confirmed New Reply → UI state clears, user can start fresh
  AC3: New Reply does not delete or modify DB records
"""

import inspect
import os

import ui_helpers

_GENERATE_PAGE = os.path.join(
    os.path.dirname(__file__), os.pardir, "pages", "0_Generate.py",
)

# ---------------------------------------------------------------------------
# Helpers / source inspection
# ---------------------------------------------------------------------------


def _source() -> str:
    return open(_GENERATE_PAGE).read()


# ---------------------------------------------------------------------------
# AC1: Unapproved draft → warn before clearing
# ---------------------------------------------------------------------------


class TestUnsavedDraftWarning:
    def test_has_unsaved_draft_function_exists(self) -> None:
        assert hasattr(ui_helpers, "_has_unsaved_draft")

    def test_unsaved_draft_true_when_reply_not_approved(self) -> None:
        """_has_unsaved_draft returns True when reply exists and not approved."""
        import streamlit as st

        st.session_state.reply_text = "draft reply"
        st.session_state.approved = False
        try:
            assert ui_helpers._has_unsaved_draft() is True
        finally:
            st.session_state.reply_text = ""
            st.session_state.approved = False

    def test_unsaved_draft_false_when_approved(self) -> None:
        import streamlit as st

        st.session_state.reply_text = "approved reply"
        st.session_state.approved = True
        try:
            assert ui_helpers._has_unsaved_draft() is False
        finally:
            st.session_state.reply_text = ""
            st.session_state.approved = False

    def test_unsaved_draft_false_when_no_reply(self) -> None:
        import streamlit as st

        st.session_state.reply_text = ""
        st.session_state.approved = False
        try:
            assert ui_helpers._has_unsaved_draft() is False
        finally:
            st.session_state.reply_text = ""
            st.session_state.approved = False

    def test_confirmation_warning_in_source(self) -> None:
        """Confirmation dialog warns about unsaved draft."""
        source = _source()
        assert "unsaved draft" in source.lower()

    def test_confirm_new_reply_state_exists(self) -> None:
        source = _source()
        assert "confirm_new_reply" in source

    def test_discard_button_in_source(self) -> None:
        source = _source()
        assert "Discard draft and start new" in source

    def test_keep_editing_button_in_source(self) -> None:
        source = _source()
        assert "Keep editing" in source


# ---------------------------------------------------------------------------
# AC2: Confirmed New Reply → UI state clears
# ---------------------------------------------------------------------------


class TestResetSession:
    def test_reset_session_function_exists(self) -> None:
        assert hasattr(ui_helpers, "_reset_session")

    def test_reset_session_clears_reply_text(self) -> None:
        import streamlit as st

        st.session_state.reply_text = "some reply"
        st.session_state.record_id = 42
        st.session_state.approved = True
        st.session_state.generation_meta = {"model_id": "test"}
        st.session_state.generating = True
        st.session_state.approving = True
        st.session_state.last_error = "error"
        st.session_state.last_error_retryable = True
        st.session_state.confirm_new_reply = True

        ui_helpers._reset_session()

        assert st.session_state.reply_text == ""
        assert st.session_state.record_id is None
        assert st.session_state.approved is False
        assert st.session_state.generation_meta is None
        assert st.session_state.generating is False
        assert st.session_state.approving is False
        assert st.session_state.last_error is None
        assert st.session_state.last_error_retryable is False
        assert st.session_state.confirm_new_reply is False

    def test_new_reply_button_in_source(self) -> None:
        source = _source()
        assert '"New Reply"' in source


# ---------------------------------------------------------------------------
# AC3: No DB records deleted or modified
# ---------------------------------------------------------------------------


class TestNoDbModification:
    def test_reset_does_not_call_db(self) -> None:
        """_reset_session only touches session state, no DB imports."""
        import dis
        import io

        output = io.StringIO()
        dis.dis(ui_helpers._reset_session, file=output)
        bytecode = output.getvalue()
        # Should not reference any DB operations
        assert "delete" not in bytecode.lower()
        assert "commit" not in bytecode.lower()

    def test_no_db_import_in_reset_function(self) -> None:
        """The _reset_session function source should not reference DB operations."""
        source = inspect.getsource(ui_helpers._reset_session)
        assert "db" not in source.lower()
        assert "session_local" not in source.lower()
        assert "delete" not in source.lower()

    def test_new_reply_section_no_db_calls(self) -> None:
        """The New Reply button section does not import or call DB functions."""
        source = _source()
        # Find the New Reply button section
        new_reply_idx = source.index('"New Reply"')
        # Check the surrounding 500 chars for DB references
        section = source[max(0, new_reply_idx - 200) : new_reply_idx + 500]
        assert "delete_record" not in section
        assert "SessionLocal" not in section
