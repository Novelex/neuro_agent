"""Repository for Task data access."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.task import Task as TaskModel
from app.schemas.task_schema import TaskCreate, TaskUpdate, TaskStatusUpdate

OPEN_STATUSES = ("open", "in_progress")


class TaskRepository:

    def get_all(
        self,
        db: Session,
        user_id: str,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[TaskModel]:
        q = db.query(TaskModel).filter(TaskModel.user_id == user_id)

        if status == "active":
            q = q.filter(TaskModel.status.in_(OPEN_STATUSES))
        elif status is not None:
            q = q.filter(TaskModel.status == status)

        q = q.order_by(TaskModel.created_at.desc())

        if offset is not None:
            q = q.offset(offset)
        if limit is not None:
            q = q.limit(limit)

        return q.all()

    def get_open(self, db: Session, user_id: str) -> List[TaskModel]:
        return (
            db.query(TaskModel)
            .filter(TaskModel.user_id == user_id, TaskModel.status.in_(OPEN_STATUSES))
            .order_by(TaskModel.created_at.asc())
            .all()
        )

    def get_by_id(self, db: Session, task_id: str, user_id: str) -> Optional[TaskModel]:
        return (
            db.query(TaskModel)
            .filter(TaskModel.id == task_id, TaskModel.user_id == user_id)
            .first()
        )

    def create(self, db: Session, user_id: str, data: TaskCreate) -> TaskModel:
        task = TaskModel(
            user_id=user_id,
            title=data.title,
            description=data.description,
            due_date=data.due_date,
            priority=data.priority,
            estimated_energy=data.estimated_energy,
            estimated_sensory_cost=data.estimated_sensory_cost,
            source=data.source,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def update(self, db: Session, task_id: str, user_id: str, data: TaskUpdate) -> Optional[TaskModel]:
        task = self.get_by_id(db, task_id, user_id)
        if not task:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)
        task.last_touched_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
        return task

    def update_status(
        self, db: Session, task_id: str, user_id: str, data: TaskStatusUpdate
    ) -> Optional[TaskModel]:
        task = self.get_by_id(db, task_id, user_id)
        if not task:
            return None
        task.status = data.status
        task.last_touched_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)
        return task

    def delete(self, db: Session, task_id: str, user_id: str) -> bool:
        task = self.get_by_id(db, task_id, user_id)
        if not task:
            return False
        db.delete(task)
        db.commit()
        return True


task_repository = TaskRepository()
