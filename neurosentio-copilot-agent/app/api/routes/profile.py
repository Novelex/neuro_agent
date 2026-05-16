"""Profile routes — GET /profile and PUT /profile."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.utils.time_utils import get_user_id
from app.repositories.user_profile_repository import user_profile_repository
from app.schemas.user_profile_schema import Profile, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=Profile, summary="Get or create user profile")
def get_profile(
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns the current user's profile.
    If no profile exists, a default profile is created and returned.
    """
    profile = user_profile_repository.get_or_create_default(db, user_id)
    return profile


@router.put("", response_model=Profile, summary="Update user profile")
def update_profile(
    body: ProfileUpdate,
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """
    Update one or more profile fields.
    Only provided fields are updated (partial update).
    """
    # Ensure the profile exists before updating
    user_profile_repository.get_or_create_default(db, user_id)
    profile = user_profile_repository.update(db, user_id, body)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
