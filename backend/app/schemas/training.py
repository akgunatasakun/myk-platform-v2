"""Training (Fiziksel Eğitim) Pydantic şemaları — Pydantic v2.

Tüm Input şemaları extra="forbid" kullanır.
Attendance status kaynağı: Flask GECERLI = {'var','yok','izinli','gecikti'}
"""
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Sabitler ──────────────────────────────────────────────────────────────────

COURSE_STATUS_VALUES = ["planlandi", "aktif", "tamamlandi", "iptal"]
SESSION_STATUS_VALUES = ["planli", "tamamlandi", "iptal"]
ENROLLMENT_STATUS_VALUES = ["active", "cancelled", "completed"]
PAYMENT_STATUS_VALUES = ["pending", "paid", "overdue"]


class AttendanceStatus(str, Enum):
    var = "var"
    yok = "yok"
    izinli = "izinli"
    gecikti = "gecikti"


class AttendanceMode(str, Enum):
    coach_daily = "coach_daily"
    adult_self_checkin = "adult_self_checkin"


# ── Yardımcı tipler ───────────────────────────────────────────────────────────

class InstructorRef(BaseModel):
    """Antrenör referansı — çıktı listesinde kullanılır."""
    id: uuid.UUID
    name: str


# ── TrainingCourse ────────────────────────────────────────────────────────────

class TrainingCourseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    class_name: Optional[str] = None
    level: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    schedule_text: Optional[str] = None
    capacity: int = Field(default=0, ge=0)
    fee: Decimal = Field(default=Decimal("0"), ge=0)
    # Çoklu antrenör — yeni alan
    instructor_person_ids: List[uuid.UUID] = Field(default_factory=list)
    # Geriye dönük uyumluluk — tek antrenör (junction'a yazılır)
    instructor_person_id: Optional[uuid.UUID] = None
    status: Literal["planlandi", "aktif", "tamamlandi", "iptal"] = "planlandi"
    attendance_mode: AttendanceMode = AttendanceMode.coach_daily
    is_registration_open: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Optional[date], info: object) -> Optional[date]:
        start = getattr(info, "data", {}).get("start_date") if hasattr(info, "data") else None
        if v is not None and start is not None and v < start:
            raise ValueError("Bitiş tarihi başlangıç tarihinden önce olamaz.")
        return v

    def effective_instructor_ids(self) -> List[uuid.UUID]:
        """instructor_person_id (eski) ve instructor_person_ids (yeni) birleştir."""
        ids: List[uuid.UUID] = list(self.instructor_person_ids)
        if self.instructor_person_id and self.instructor_person_id not in ids:
            ids.insert(0, self.instructor_person_id)
        return ids


class TrainingCourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    class_name: Optional[str] = None
    level: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    schedule_text: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=0)
    fee: Optional[Decimal] = Field(default=None, ge=0)
    # Çoklu antrenör — yeni alan (None = değiştirme)
    instructor_person_ids: Optional[List[uuid.UUID]] = None
    # Geriye dönük uyumluluk
    instructor_person_id: Optional[uuid.UUID] = None
    status: Optional[Literal["planlandi", "aktif", "tamamlandi", "iptal"]] = None
    is_active: Optional[bool] = None
    attendance_mode: Optional[AttendanceMode] = None
    is_registration_open: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v

    def has_instructor_update(self) -> bool:
        return self.instructor_person_ids is not None or self.instructor_person_id is not None

    def effective_instructor_ids(self) -> List[uuid.UUID]:
        """Güncellenecek antrenör listesini döndür."""
        if self.instructor_person_ids is not None:
            ids = list(self.instructor_person_ids)
            if self.instructor_person_id and self.instructor_person_id not in ids:
                ids.insert(0, self.instructor_person_id)
            return ids
        if self.instructor_person_id is not None:
            return [self.instructor_person_id]
        return []


class TrainingCourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    name: str
    description: Optional[str] = None
    class_name: Optional[str] = None
    level: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    schedule_text: Optional[str] = None
    capacity: int
    fee: Decimal
    # Geriye dönük uyumluluk (ilk antrenörden doldurulur)
    instructor_person_id: Optional[uuid.UUID] = None
    instructor_name: Optional[str] = None
    # Yeni — çoklu antrenör listesi
    instructors: List[InstructorRef] = Field(default_factory=list)
    status: str
    attendance_mode: str = "coach_daily"
    is_active: bool
    is_deleted: bool
    is_registration_open: bool = True
    enrollment_count: int = 0
    created_at: datetime
    updated_at: datetime


class TrainingCourseListOut(BaseModel):
    items: List[TrainingCourseOut]
    total: int
    skip: int
    limit: int


# ── TrainingSession ───────────────────────────────────────────────────────────

class TrainingSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    # Çoklu antrenör
    instructor_person_ids: List[uuid.UUID] = Field(default_factory=list)
    # Geriye dönük uyumluluk
    instructor_person_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    status: Literal["planli", "tamamlandi", "iptal"] = "planli"

    def effective_instructor_ids(self) -> List[uuid.UUID]:
        ids: List[uuid.UUID] = list(self.instructor_person_ids)
        if self.instructor_person_id and self.instructor_person_id not in ids:
            ids.insert(0, self.instructor_person_id)
        return ids


class TrainingSessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    # Çoklu antrenör
    instructor_person_ids: Optional[List[uuid.UUID]] = None
    # Geriye dönük uyumluluk
    instructor_person_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    status: Optional[Literal["planli", "tamamlandi", "iptal"]] = None

    def has_instructor_update(self) -> bool:
        return self.instructor_person_ids is not None or self.instructor_person_id is not None

    def effective_instructor_ids(self) -> List[uuid.UUID]:
        if self.instructor_person_ids is not None:
            ids = list(self.instructor_person_ids)
            if self.instructor_person_id and self.instructor_person_id not in ids:
                ids.insert(0, self.instructor_person_id)
            return ids
        if self.instructor_person_id is not None:
            return [self.instructor_person_id]
        return []


class TrainingSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    course_id: uuid.UUID
    session_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    # Geriye dönük uyumluluk
    instructor_person_id: Optional[uuid.UUID] = None
    instructor_name: Optional[str] = None
    # Yeni
    instructors: List[InstructorRef] = Field(default_factory=list)
    status: str
    notes: Optional[str] = None
    attendance_count: int = 0
    created_at: datetime
    updated_at: datetime


# ── TrainingEnrollment ────────────────────────────────────────────────────────

class TrainingEnrollmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: uuid.UUID
    notes: Optional[str] = None


class TrainingEnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    course_id: uuid.UUID
    person_id: uuid.UUID
    person_name: Optional[str] = None           # computed
    status: str
    payment_status: str
    notes: Optional[str] = None
    enrolled_at: datetime
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ── TrainingAttendance ────────────────────────────────────────────────────────

class AttendanceRecord(BaseModel):
    """Toplu yoklama girişinde tek kişi kaydı."""
    model_config = ConfigDict(extra="forbid")

    person_id: uuid.UUID
    status: AttendanceStatus
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    notes: Optional[str] = None


class AttendanceBulkUpdate(BaseModel):
    """PUT /attendance body — toplu UPSERT."""
    model_config = ConfigDict(extra="forbid")

    records: List[AttendanceRecord] = Field(..., min_length=1)


class TrainingAttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    club_id: uuid.UUID
    session_id: uuid.UUID
    person_id: uuid.UUID
    person_name: Optional[str] = None           # computed
    status: str
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    notes: Optional[str] = None
    recorded_by_user_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class AttendanceBulkResult(BaseModel):
    """PUT /attendance response."""
    updated: int
    created: int


# ── Attendance Report ─────────────────────────────────────────────────────────

class AttendancePersonSummary(BaseModel):
    person_id: uuid.UUID
    person_name: str
    var: int = 0
    yok: int = 0
    izinli: int = 0
    gecikti: int = 0
    toplam_oturum: int = 0
    devam_yuzdesi: float = 0.0


class AttendanceReport(BaseModel):
    course_id: uuid.UUID
    course_name: str
    toplam_oturum: int
    katilimcilar: List[AttendancePersonSummary]


# ── Self Check-in (Sporcu) ────────────────────────────────────────────────────

class SelfCheckinSessionOut(BaseModel):
    """Sporcu kendi yaklaşan adult_self_checkin oturumlarını bu şemayla alır."""
    session_id: uuid.UUID
    course_id: uuid.UUID
    course_name: str
    session_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    window_open: bool
    window_note: str   # örn. "09:00 – 10:00 arasında açık" veya "Tüm gün açık (aynı gün)"
    my_status: Optional[str] = None  # 'var', 'yok', 'izinli', 'gecikti' veya None
