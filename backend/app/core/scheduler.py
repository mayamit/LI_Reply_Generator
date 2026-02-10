"""Lightweight repeating-job scheduler using stdlib threading.

Runs a callable at a fixed interval in a daemon thread.  Exceptions in the
job are logged but never propagate — the app continues running (AC2).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from backend.app.db.session import SessionLocal
from backend.app.services.score_recomputation import recompute_all_scores

logger = logging.getLogger(__name__)


class RepeatingJob:
    """Execute *func* every *interval_seconds* in a background daemon thread."""

    def __init__(self, func: Callable[[], None], interval_seconds: float) -> None:
        self._func = func
        self._interval = interval_seconds
        self._stop_event = threading.Event()
        self._timer: threading.Timer | None = None

    def _run(self) -> None:
        if self._stop_event.is_set():
            return
        try:
            self._func()
        except Exception:
            logger.exception("repeating_job_error: job=%s", self._func.__name__)
        # Schedule next run regardless of success/failure
        self._schedule()

    def _schedule(self) -> None:
        if self._stop_event.is_set():
            return
        self._timer = threading.Timer(self._interval, self._run)
        self._timer.daemon = True
        self._timer.start()

    def start(self) -> None:
        """Start the repeating job (first execution after one interval)."""
        logger.info(
            "repeating_job_started: job=%s interval=%ds",
            self._func.__name__,
            self._interval,
        )
        self._stop_event.clear()
        self._schedule()

    def stop(self) -> None:
        """Signal the job to stop and cancel any pending timer."""
        self._stop_event.set()
        if self._timer is not None:
            self._timer.cancel()
        logger.info("repeating_job_stopped: job=%s", self._func.__name__)


# ---------------------------------------------------------------------------
# Module-level scheduler instance for score recomputation
# ---------------------------------------------------------------------------

_score_job: RepeatingJob | None = None


def _run_score_recomputation() -> None:
    """Create a DB session, recompute scores, then commit and close."""
    db = SessionLocal()
    try:
        recompute_all_scores(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def start_score_recomputation_scheduler(interval_seconds: int) -> None:
    """Start the background score recomputation job."""
    global _score_job  # noqa: PLW0603
    if _score_job is not None:
        _score_job.stop()
    _score_job = RepeatingJob(_run_score_recomputation, interval_seconds)
    _score_job.start()


def stop_score_recomputation_scheduler() -> None:
    """Stop the background score recomputation job if running."""
    global _score_job  # noqa: PLW0603
    if _score_job is not None:
        _score_job.stop()
        _score_job = None
