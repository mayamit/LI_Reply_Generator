"""CRUD endpoints for reply presets."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.presets import ReplyPreset
from backend.app.services.preset_repository import (
    PresetNotFoundError,
    PresetValidationError,
    create_preset,
    delete_preset,
    get_preset,
    list_presets,
    update_preset,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/v1/presets", response_model=list[ReplyPreset])
def list_all_presets(db: Session = Depends(get_db)) -> list[ReplyPreset]:
    """Return all presets."""
    return list_presets(db)


@router.get("/api/v1/presets/{preset_id}", response_model=ReplyPreset)
def get_one_preset(preset_id: str, db: Session = Depends(get_db)) -> ReplyPreset:
    """Return a single preset by ID."""
    try:
        return get_preset(db, preset_id)
    except PresetNotFoundError:
        raise HTTPException(status_code=404, detail=f"Preset not found: {preset_id}")


@router.post("/api/v1/presets", response_model=ReplyPreset, status_code=201)
def create_new_preset(preset: ReplyPreset, db: Session = Depends(get_db)) -> ReplyPreset:
    """Create a new preset."""
    try:
        return create_preset(db, preset)
    except PresetValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.put("/api/v1/presets/{preset_id}", response_model=ReplyPreset)
def update_existing_preset(
    preset_id: str, preset: ReplyPreset, db: Session = Depends(get_db),
) -> ReplyPreset:
    """Update an existing preset."""
    try:
        return update_preset(db, preset_id, preset)
    except PresetNotFoundError:
        raise HTTPException(status_code=404, detail=f"Preset not found: {preset_id}")


@router.delete("/api/v1/presets/{preset_id}", status_code=204)
def delete_existing_preset(preset_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a preset."""
    try:
        delete_preset(db, preset_id)
    except PresetNotFoundError:
        raise HTTPException(status_code=404, detail=f"Preset not found: {preset_id}")
    except PresetValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
