import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskStatus = Literal["acik", "devam_ediyor", "tamamlandi", "iptal"]
TaskPriority = Literal["dusuk", "normal", "yuksek", "acil"]


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    assigned_person_id: uuid.UUID | None = None
    due_date: date | None = None
    priority: TaskPriority = "normal"
    status: TaskStatus = "acik"

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Görev başlığı boş olamaz.")
        return value.strip()


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    assigned_person_id: uuid.UUID | None = None
    due_date: date | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None

    @field_validator("title", "priority", "status")
    @classmethod
    def required_if_present(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("Bu alan boş olamaz.")
        return value.strip()


class TaskOut(TaskCreate):
    id: uuid.UUID
    assigned_person_name: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskListOut(BaseModel):
    items: list[TaskOut]
    total: int
    skip: int
    limit: int


class TaskAssignee(BaseModel):
    id: uuid.UUID
    name: str
