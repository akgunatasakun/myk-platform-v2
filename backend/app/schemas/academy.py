"""Academy Pydantic v2 şemaları.

GÜVENLİK KURALI: correct_letter HİÇBİR response schema'da BULUNMAMALI.
Quiz doğrulaması yalnızca backend service katmanında yapılır.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Program ───────────────────────────────────────────────────────────────────

class AcademyLessonStepOut(BaseModel):
    id: uuid.UUID
    sira: int
    tip: str
    baslik: Optional[str] = None
    data_json: Optional[dict] = None

    model_config = {"from_attributes": True}


class AcademyLessonOut(BaseModel):
    id: uuid.UUID
    slug: str
    ad: str
    aciklama: Optional[str] = None
    ders_tipi: str
    tahmini_sure_dk: Optional[int] = None
    sira: int
    steps: list[AcademyLessonStepOut] = []

    model_config = {"from_attributes": True}


class AcademyModuleOut(BaseModel):
    id: uuid.UUID
    slug: str
    ad: str
    sira: int
    lessons: list[AcademyLessonOut] = []

    model_config = {"from_attributes": True}


class AcademyProgramOut(BaseModel):
    id: uuid.UUID
    slug: str
    ad: str
    kod: str
    aciklama: Optional[str] = None
    seviye: int
    modules: list[AcademyModuleOut] = []

    model_config = {"from_attributes": True}


class AcademyProgramListItem(BaseModel):
    id: uuid.UUID
    slug: str
    ad: str
    kod: str
    seviye: int

    model_config = {"from_attributes": True}


# ── Enrollment ────────────────────────────────────────────────────────────────

class EnrollmentOut(BaseModel):
    id: uuid.UUID
    program_id: uuid.UUID
    status: str
    enrolled_at: datetime

    model_config = {"from_attributes": True}


class EnrollmentCreate(BaseModel):
    program_id: uuid.UUID
    # club_id ve person_id JWT'den alınır — body'de BULUNMAMALI

    model_config = {"extra": "forbid"}


# ── Session ───────────────────────────────────────────────────────────────────

class SessionOut(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    started_at: datetime

    model_config = {"from_attributes": True}


# ── Progress ──────────────────────────────────────────────────────────────────

class ProgressOut(BaseModel):
    lesson_id: uuid.UUID
    tamamlandi: bool
    yuzde: int
    toplam_sure_sn: int
    son_adim_sira: Optional[int] = None

    model_config = {"from_attributes": True}


# ── Quiz ──────────────────────────────────────────────────────────────────────

class QuizQuestionOut(BaseModel):
    """Quiz sorusu — correct_letter BULUNMAMALI (güvenlik kuralı)."""
    id: uuid.UUID
    sira: int
    soru_metni: str
    options: list[dict]  # [{"harf": "A", "metin": "..."}]
    # correct_letter kasıtlı olarak dışarıda bırakıldı

    model_config = {"from_attributes": True}


class QuizAnswerIn(BaseModel):
    question_id: uuid.UUID
    secilen_harf: str  # "A", "B", "C", "D"

    model_config = {"extra": "forbid"}


class QuizAttemptOut(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    basladi_at: datetime
    bitti_at: Optional[datetime] = None
    dogru: int
    toplam: int
    gecti: Optional[bool] = None

    model_config = {"from_attributes": True}


class QuizAttemptStartOut(BaseModel):
    """Quiz başlatma response — attempt + sorular."""
    attempt: QuizAttemptOut
    questions: list[QuizQuestionOut]


class QuizAttemptResult(BaseModel):
    """Quiz bitirme response — doğru cevaplar bitişte gösterilebilir."""
    attempt_id: uuid.UUID
    dogru: int
    toplam: int
    gecti: bool
    # Bitişte doğru cevaplar soru bazında gösterilir (correct_letter dahil —
    # quiz BİTMİŞ olduğundan artık güvenlik riski oluşturmaz)
    sorular: list[dict]  # [{soru_metni, secilen, dogru_harf, dogru_mu, aciklama}]
