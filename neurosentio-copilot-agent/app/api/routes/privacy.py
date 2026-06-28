"""Privacy and Data Controls API Router."""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.schemas.privacy_schema import (
    PrivacyPreferencesResponse,
    PrivacyPreferencesUpdate,
    PrivacyAuditLogResponse,
)
from app.repositories.privacy_preferences_repository import privacy_preferences_repository
from app.repositories.privacy_audit_repository import privacy_audit_repository
from app.services.data_export_service import export_user_data
from app.services.data_delete_service import delete_user_data
from app.services.data_retention_service import apply_retention_policies

router = APIRouter(tags=["Privacy"])


# ──────────────────────────────────────────────
# GET /privacy/preferences
# ──────────────────────────────────────────────
@router.get(
    "/privacy/preferences",
    response_model=PrivacyPreferencesResponse,
    summary="Get user privacy preferences",
)
def get_preferences(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieve granular privacy preferences for the current user.
    Creates default preferences if they don't exist yet.
    """
    return privacy_preferences_repository.get_or_create_default(db, user_id)


# ──────────────────────────────────────────────
# PATCH /privacy/preferences
# ──────────────────────────────────────────────
@router.patch(
    "/privacy/preferences",
    response_model=PrivacyPreferencesResponse,
    summary="Update user privacy preferences",
)
def update_preferences(
    body: PrivacyPreferencesUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Update granular privacy and data retention preferences.
    Saves an entry in the privacy audit log listing which fields were modified.
    """
    # Track which fields are explicitly being updated
    updated_fields = list(body.model_dump(exclude_unset=True).keys())
    
    updated = privacy_preferences_repository.update(db, user_id, body)
    
    # Log the action in privacy audit log
    privacy_audit_repository.log_privacy_action(
        db=db,
        user_id=user_id,
        action_type="update_preferences",
        extra_metadata={"updated_fields": updated_fields}
    )
    
    return updated


# ──────────────────────────────────────────────
# GET /privacy/audit-log
# ──────────────────────────────────────────────
@router.get(
    "/privacy/audit-log",
    response_model=List[PrivacyAuditLogResponse],
    summary="Get privacy audit logs",
)
def get_audit_logs(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Retrieve privacy audit logs for the current user in reverse chronological order.
    These logs only track metadata and actions (never sensitive text).
    """
    return privacy_audit_repository.get_audit_logs(db, user_id)


# ──────────────────────────────────────────────
# GET /user/export-data
# ──────────────────────────────────────────────
@router.get(
    "/user/export-data",
    summary="Export all user data",
)
def export_data(
    redacted: bool = Query(default=False, description="Strip sensitive fields in memory before exporting"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Export all owned user data across all 14 database models in structured JSON format.
    If redacted=true, masks sensitive fields strictly in memory (does NOT mutate stored SQLite database rows).
    """
    data = export_user_data(db, user_id, redacted=redacted)
    return JSONResponse(content=data)


# ──────────────────────────────────────────────
# DELETE /user/delete-data
# ──────────────────────────────────────────────
@router.delete(
    "/user/delete-data",
    summary="Delete all user data",
)
def delete_data(
    confirm: bool = Query(default=False, description="Must be true to proceed with deletion"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Permanently erase all user owned data in proper dependency order across all tables.
    Also deletes user-linked audit logs and privacy preferences.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must pass confirm=true to verify full deletion",
        )
    
    counts = delete_user_data(db, user_id, delete_profile=True)
    return {
        "status": "success",
        "message": "All user data has been permanently deleted in correct dependency sequence.",
        "deleted_counts": counts,
    }


# ──────────────────────────────────────────────
# POST /privacy/apply-retention
# ──────────────────────────────────────────────
@router.post(
    "/privacy/apply-retention",
    summary="Apply data retention policies manually",
)
def apply_retention(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Manually execute data retention policies to prune expired records.
    Prunes records based on user's current retention settings.
    """
    counts = apply_retention_policies(db, user_id)
    return {
        "status": "success",
        "message": "Data retention policy applied successfully.",
        "pruned_counts": counts,
    }
