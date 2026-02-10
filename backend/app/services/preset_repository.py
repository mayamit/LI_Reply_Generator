"""Repository for preset CRUD operations."""

from __future__ import annotations

import json
import logging

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.models.preset_record import PresetRecord
from backend.app.models.presets import ReplyPreset

logger = logging.getLogger(__name__)


class PresetNotFoundError(Exception):
    """Raised when a preset cannot be found by id."""


class PresetValidationError(Exception):
    """Raised when a preset operation violates business rules."""


def _row_to_reply_preset(row: PresetRecord) -> ReplyPreset:
    """Convert a DB row to a ReplyPreset Pydantic model."""
    bullets = None
    if row.guidance_bullets:
        try:
            bullets = json.loads(row.guidance_bullets)
        except (json.JSONDecodeError, TypeError):
            bullets = None
    return ReplyPreset(
        id=row.id,
        label=row.label,
        tone=row.tone,
        length_bucket=row.length_bucket,
        intent=row.intent,
        description=row.description,
        guidance_bullets=bullets,
        allow_hashtags=row.allow_hashtags,
        is_default=row.is_default,
    )


def list_presets(db: Session) -> list[ReplyPreset]:
    """Return all presets ordered by label."""
    rows = db.query(PresetRecord).order_by(PresetRecord.label).all()
    return [_row_to_reply_preset(r) for r in rows]


def get_preset(db: Session, preset_id: str) -> ReplyPreset:
    """Fetch a single preset by ID.

    Raises:
        PresetNotFoundError: If no preset with *preset_id* exists.
    """
    row = db.get(PresetRecord, preset_id)
    if row is None:
        raise PresetNotFoundError(f"Preset not found: id={preset_id}")
    return _row_to_reply_preset(row)


def create_preset(db: Session, preset: ReplyPreset) -> ReplyPreset:
    """Insert a new preset.

    Raises:
        PresetValidationError: If the ID already exists.
    """
    existing = db.get(PresetRecord, preset.id)
    if existing is not None:
        raise PresetValidationError(f"Preset with id '{preset.id}' already exists")

    # If new preset is default, clear existing default
    if preset.is_default:
        _clear_default(db)

    row = PresetRecord(
        id=preset.id,
        label=preset.label,
        tone=preset.tone,
        length_bucket=preset.length_bucket,
        intent=preset.intent,
        description=preset.description,
        guidance_bullets=json.dumps(preset.guidance_bullets) if preset.guidance_bullets else None,
        allow_hashtags=preset.allow_hashtags,
        is_default=preset.is_default,
    )
    db.add(row)
    db.commit()
    logger.info("preset_created: id=%s", preset.id)
    return _row_to_reply_preset(row)


def update_preset(db: Session, preset_id: str, preset: ReplyPreset) -> ReplyPreset:
    """Update an existing preset.

    Raises:
        PresetNotFoundError: If no preset with *preset_id* exists.
    """
    row = db.get(PresetRecord, preset_id)
    if row is None:
        raise PresetNotFoundError(f"Preset not found: id={preset_id}")

    # If setting this as default, clear existing default first
    if preset.is_default and not row.is_default:
        _clear_default(db)

    row.label = preset.label
    row.tone = preset.tone
    row.length_bucket = preset.length_bucket
    row.intent = preset.intent
    row.description = preset.description
    row.guidance_bullets = json.dumps(preset.guidance_bullets) if preset.guidance_bullets else None
    row.allow_hashtags = preset.allow_hashtags
    row.is_default = preset.is_default
    db.commit()
    logger.info("preset_updated: id=%s", preset_id)
    return _row_to_reply_preset(row)


def delete_preset(db: Session, preset_id: str) -> None:
    """Delete a preset by ID.

    Raises:
        PresetNotFoundError: If no preset with *preset_id* exists.
        PresetValidationError: If the preset is the default.
    """
    row = db.get(PresetRecord, preset_id)
    if row is None:
        raise PresetNotFoundError(f"Preset not found: id={preset_id}")
    if row.is_default:
        raise PresetValidationError("Cannot delete the default preset. Set another preset as default first.")
    db.delete(row)
    db.commit()
    logger.info("preset_deleted: id=%s", preset_id)


def _clear_default(db: Session) -> None:
    """Clear the is_default flag on all presets."""
    db.query(PresetRecord).filter(PresetRecord.is_default.is_(True)).update(
        {"is_default": False}
    )
