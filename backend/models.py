"""
models.py
---------
SQLAlchemy ORM table definition for the Task entity.
Mirrors the Pydantic schemas exactly so the backend ↔ frontend
data contract is always consistent.
"""

from sqlalchemy import Column, Integer, String, Date, Enum as SAEnum
from database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    title = Column(String(255), nullable=False)

    description = Column(String(2000), nullable=False, default="")

    due_date = Column(Date, nullable=True)

    status = Column(
        SAEnum("To-Do", "In Progress", "Done", name="status_enum"),
        nullable=False,
        default="To-Do",
    )

    # Soft foreign key — kept loose to allow orphan cleanup on delete
    # without cascade complexity. Validated at the application layer.
    blocked_by = Column(Integer, nullable=True)

    recurring = Column(
        SAEnum("None", "Daily", "Weekly", name="recurring_enum"),
        nullable=False,
        default="None",
    )
