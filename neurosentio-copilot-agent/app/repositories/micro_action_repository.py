"""Repository for MicroAction data access."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.micro_action import MicroAction as MicroActionModel
from app.schemas.micro_action_schema import MicroActionCreate, MicroActionUpdate, MicroActionStatusUpdate


class MicroActionRepository:
    """
    All methods filter by user_id.
    A user can never access another user's micro-actions.
    """

    # ──────────────────────────────────────────────────────────────────
    # Reads
    # ──────────────────────────────────────────────────────────────────

    def get_by_id(
        self, db: Session, user_id: str, micro_action_id: str
    ) -> Optional[MicroActionModel]:
        return (
            db.query(MicroActionModel)
            .filter(
                MicroActionModel.id == micro_action_id,
                MicroActionModel.user_id == user_id,
            )
            .first()
        )

    def get_by_task(
        self, db: Session, user_id: str, task_id: str
    ) -> List[MicroActionModel]:
        return (
            db.query(MicroActionModel)
            .filter(
                MicroActionModel.user_id == user_id,
                MicroActionModel.task_id == task_id,
            )
            .order_by(MicroActionModel.sort_order.asc(), MicroActionModel.created_at.asc())
            .all()
        )

    def get_open_by_task(
        self, db: Session, user_id: str, task_id: str
    ) -> List[MicroActionModel]:
        return (
            db.query(MicroActionModel)
            .filter(
                MicroActionModel.user_id == user_id,
                MicroActionModel.task_id == task_id,
                MicroActionModel.status == "open",
            )
            .order_by(MicroActionModel.sort_order.asc(), MicroActionModel.created_at.asc())
            .all()
        )

    # ──────────────────────────────────────────────────────────────────
    # Writes
    # ──────────────────────────────────────────────────────────────────

    def create_many(
        self,
        db: Session,
        user_id: str,
        task_id: str,
        micro_actions: List[MicroActionCreate],
        plan_id: Optional[str] = None,
    ) -> List[MicroActionModel]:
        """
        Bulk-insert a list of MicroActionCreate objects.
        Assigns sort_order from the list position if not explicitly set.
        Stores parent_micro_action_id if provided.
        """
        created = []
        for idx, data in enumerate(micro_actions):
            row = MicroActionModel(
                user_id=user_id,
                task_id=task_id,
                plan_id=plan_id,
                parent_micro_action_id=getattr(data, "parent_micro_action_id", None),
                title=data.title,
                description=data.description,
                duration_minutes=data.duration_minutes,
                energy_cost=data.energy_cost,
                sensory_cost=data.sensory_cost,
                friction_level=data.friction_level,
                sort_order=data.sort_order if data.sort_order else idx,
                status="open",
            )
            db.add(row)
            created.append(row)
        db.commit()
        for row in created:
            db.refresh(row)
        return created

    def set_status_direct(
        self, db: Session, user_id: str, micro_action_id: str, status: str
    ) -> Optional[MicroActionModel]:
        """Set status directly without going through the schema — used internally."""
        row = self.get_by_id(db, user_id, micro_action_id)
        if not row:
            return None
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row

    def get_open_by_plan(
        self, db: Session, user_id: str, plan_id: str
    ) -> List[MicroActionModel]:
        """Returns all open micro-actions linked to a specific morning plan."""
        return (
            db.query(MicroActionModel)
            .filter(
                MicroActionModel.user_id == user_id,
                MicroActionModel.plan_id == plan_id,
                MicroActionModel.status == "open",
            )
            .order_by(MicroActionModel.sort_order.asc())
            .all()
        )

    def update_status(
        self,
        db: Session,
        user_id: str,
        micro_action_id: str,
        data: MicroActionStatusUpdate,
    ) -> Optional[MicroActionModel]:
        row = self.get_by_id(db, user_id, micro_action_id)
        if not row:
            return None
        row.status = data.status
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row

    def update_micro_action(
        self,
        db: Session,
        user_id: str,
        micro_action_id: str,
        data: MicroActionUpdate,
    ) -> Optional[MicroActionModel]:
        row = self.get_by_id(db, user_id, micro_action_id)
        if not row:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return row

    def delete_open_for_task(
        self, db: Session, user_id: str, task_id: str
    ) -> int:
        """
        Deletes only open micro-actions for a task.
        Done/snoozed/skipped/deferred are preserved.
        Returns the number of rows deleted.
        """
        rows = self.get_open_by_task(db, user_id, task_id)
        for row in rows:
            db.delete(row)
        db.commit()
        return len(rows)

    def delete_for_task(
        self, db: Session, user_id: str, task_id: str
    ) -> int:
        """
        Deletes ALL micro-actions for a task regardless of status.
        Used only when explicitly requested.
        Returns the number of rows deleted.
        """
        rows = self.get_by_task(db, user_id, task_id)
        for row in rows:
            db.delete(row)
        db.commit()
        return len(rows)

    def get_max_sort_order(
        self, db: Session, user_id: str, task_id: str
    ) -> int:
        """Returns the highest current sort_order value for a task's micro-actions."""
        rows = self.get_by_task(db, user_id, task_id)
        if not rows:
            return -1
        return max(r.sort_order for r in rows)


micro_action_repository = MicroActionRepository()
