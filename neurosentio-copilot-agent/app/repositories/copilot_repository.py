"""Repository for CopilotPlan data access."""

from datetime import date, datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.copilot_plan import CopilotPlan


class CopilotRepository:

    def get_by_date(self, db: Session, user_id: str, plan_date: date) -> Optional[CopilotPlan]:
        return (
            db.query(CopilotPlan)
            .filter(CopilotPlan.user_id == user_id, CopilotPlan.plan_date == plan_date)
            .order_by(CopilotPlan.created_at.desc())
            .first()
        )

    # Alias used by morning_plan_service
    def get_plan_for_date(self, db: Session, user_id: str, plan_date: date) -> Optional[CopilotPlan]:
        return self.get_by_date(db, user_id, plan_date)

    def get_today_plan(self, db: Session, user_id: str) -> Optional[CopilotPlan]:
        return self.get_by_date(db, user_id, date.today())

    def get_latest(self, db: Session, user_id: str) -> Optional[CopilotPlan]:
        return (
            db.query(CopilotPlan)
            .filter(CopilotPlan.user_id == user_id)
            .order_by(CopilotPlan.plan_date.desc())
            .first()
        )

    def upsert_today(
        self,
        db: Session,
        user_id: str,
        mode: str,
        summary: str,
        payload: dict,
    ) -> CopilotPlan:
        """Create or update today's plan."""
        today = date.today()
        plan = self.get_by_date(db, user_id, today)
        if plan:
            plan.mode = mode
            plan.summary = summary
            plan.generated_payload = payload
            plan.updated_at = datetime.now(timezone.utc)
        else:
            plan = CopilotPlan(
                user_id=user_id,
                plan_date=today,
                mode=mode,
                summary=summary,
                generated_payload=payload,
            )
            db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan


copilot_repository = CopilotRepository()
