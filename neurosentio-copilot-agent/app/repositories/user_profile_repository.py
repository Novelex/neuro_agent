"""Repository for UserProfile data access."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user_profile import UserProfile
from app.schemas.user_profile_schema import ProfileCreate, ProfileUpdate


class UserProfileRepository:

    def get_by_user_id(self, db: Session, user_id: str) -> Optional[UserProfile]:
        return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    def create(self, db: Session, data: ProfileCreate) -> UserProfile:
        profile = UserProfile(
            user_id=data.user_id,
            preferred_tone=data.preferred_tone,
            max_reply_length=data.max_reply_length,
            peak_energy_hours=data.peak_energy_hours,
            low_energy_hours=data.low_energy_hours,
            sensory_triggers=data.sensory_triggers,
            recovery_preferences=data.recovery_preferences,
            transition_support_needed=data.transition_support_needed,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    def get_or_create_default(self, db: Session, user_id: str) -> UserProfile:
        """Return existing profile or create a sensible default."""
        profile = self.get_by_user_id(db, user_id)
        if not profile:
            profile = self.create(db, ProfileCreate(user_id=user_id))
        return profile

    def update(self, db: Session, user_id: str, data: ProfileUpdate) -> Optional[UserProfile]:
        profile = self.get_by_user_id(db, user_id)
        if not profile:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)
        profile.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(profile)
        return profile


user_profile_repository = UserProfileRepository()
