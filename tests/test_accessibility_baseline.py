"""Tests for Story 5.4: Accessibility baseline for primary screens.

Covers acceptance criteria:
  AC1: Logical keyboard focus/tab order (verified via source structure)
  AC2: Validation errors clearly associated with relevant fields
  AC3: Primary actions have clear labels and are distinguishable
"""

import inspect
from pathlib import Path

_PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"


def _read_detail_source() -> str:
    return (_PAGES_DIR / "2_Detail.py").read_text()


def _read_history_source() -> str:
    return (_PAGES_DIR / "1_History.py").read_text()


# ---------------------------------------------------------------------------
# AC1: Logical tab order — form fields appear in a sensible sequence
# ---------------------------------------------------------------------------


class TestLogicalTabOrder:
    def test_main_page_form_fields_ordered(self) -> None:
        """Post text appears before optional fields in source order."""
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        post_text_pos = source.index("Paste the LinkedIn post")
        author_name_pos = source.index('"Author name"')
        assert post_text_pos < author_name_pos

    def test_optional_fields_grouped(self) -> None:
        """Optional context fields are grouped under a subheader."""
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        subheader_pos = source.index('"Optional Context"')
        author_pos = source.index('"Author name"')
        assert subheader_pos < author_pos

    def test_history_filters_before_records(self) -> None:
        """Filters appear before record listing in History page."""
        source = _read_history_source()
        filter_pos = source.index("Filters")
        records_pos = source.index("for record in records")
        assert filter_pos < records_pos


# ---------------------------------------------------------------------------
# AC2: Validation errors clearly associated with relevant fields
# ---------------------------------------------------------------------------


class TestFieldAssociatedErrors:
    def test_field_hints_defined_for_key_fields(self) -> None:
        """_FIELD_HINTS maps key input fields to actionable messages."""
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        assert "_FIELD_HINTS" in source
        for field in ["post_text", "article_text", "post_url", "author_name"]:
            assert field in source

    def test_help_text_on_post_text(self) -> None:
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        assert 'help="Required' in source

    def test_help_text_on_author_name(self) -> None:
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        assert "max 200 characters" in source

    def test_help_text_on_author_profile_url(self) -> None:
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        assert "LinkedIn profile URL" in source

    def test_help_text_on_post_url(self) -> None:
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        assert "Direct link to the LinkedIn post" in source

    def test_help_text_on_article_text(self) -> None:
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        assert "max 50,000 characters" in source

    def test_help_text_on_image_ref(self) -> None:
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        assert "max 2,000 characters" in source

    def test_help_text_on_history_author_filter(self) -> None:
        source = _read_history_source()
        assert "help=" in source


# ---------------------------------------------------------------------------
# AC3: Primary actions have clear labels and are distinguishable
# ---------------------------------------------------------------------------


class TestPrimaryActionLabels:
    def test_generate_button_is_primary(self) -> None:
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        # form_submit_button with type="primary"
        assert 'type="primary"' in source

    def test_approve_button_has_primary_type(self) -> None:
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        assert '"Approve & Save"' in source
        # Approve uses type="primary"
        approve_idx = source.index('"Approve & Save"')
        nearby = source[approve_idx : approve_idx + 200]
        assert 'type="primary"' in nearby

    def test_copy_button_has_clear_label(self) -> None:
        import streamlit_app

        source = inspect.getsource(streamlit_app)
        assert '"Copy to Clipboard"' in source

    def test_delete_button_label_distinct(self) -> None:
        source = _read_detail_source()
        assert '"Delete Record"' in source
        # Delete uses secondary type
        delete_idx = source.index('"Delete Record"')
        nearby = source[delete_idx : delete_idx + 200]
        assert 'type="secondary"' in nearby

    def test_history_column_headers_present(self) -> None:
        source = _read_history_source()
        for header in ["**Author**", "**Preset**", "**Status**", "**Date**", "**Action**"]:
            assert header in source


# ---------------------------------------------------------------------------
# Detail page: visible labels (no collapsed label_visibility)
# ---------------------------------------------------------------------------


class TestDetailPageLabels:
    def test_no_collapsed_labels(self) -> None:
        """Text areas on detail page should not hide labels from screen readers."""
        source = _read_detail_source()
        assert "label_visibility" not in source

    def test_text_area_labels_descriptive(self) -> None:
        source = _read_detail_source()
        assert '"Original post text"' in source
        assert '"Generated reply text"' in source
        assert '"Final approved reply text"' in source

    def test_delete_error_no_raw_exception(self) -> None:
        """Delete error should not expose raw exception details."""
        source = _read_detail_source()
        assert "f\"Deletion failed: {exc}\"" not in source
        assert "unexpected error" in source.lower()
