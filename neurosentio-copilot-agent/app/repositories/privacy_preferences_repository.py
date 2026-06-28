"""Repository for PrivacyPreferences data access."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.privacy_preferences import PrivacyPreferences
from app.schemas.privacy_schema import PrivacyPreferencesUpdate


class PrivacyPreferencesRepository:

    def get_by_user_id(self, db: Session, user_id: str) -> Optional[PrivacyPreferences]:
        return db.query(PrivacyPreferences).filter(PrivacyPreferences.user_id == user_id).first()

    def create_default(self, db: Session, user_id: str) -> PrivacyPreferences:
        prefs = PrivacyPreferences(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
        return prefs

    def get_or_create_default(self, db: Session, user_id: str) -> PrivacyPreferences:
        prefs = self.get_by_user_id(db, user_id)
        if not prefs:
            prefs = self.create_default(db, user_id)
        return prefs

    def update(self, db: Session, user_id: str, data: PrivacyPreferencesUpdate) -> Optional[PrivacyPreferences]:
        prefs = self.get_or_create_default(db, user_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(prefs, field, value)
        prefs.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(prefs)
        return prefs

    def delete(self, db: Session, user_id: str) -> bool:
        prefs = self.get_by_user_id(db, user_id)
        if prefs:
            db.delete(prefs)
            db.commit()
            return True
        return False


privacy_preferences_repository = PrivacyPreferencesRepository()
