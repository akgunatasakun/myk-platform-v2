"""Academy seed — idempotent. D1 programı, gemici-baglari modülü, izbarco dersi.

Kullanım:
    python -m scripts.seed_academy
    python backend/scripts/seed_academy.py

Quiz cevapları yalnızca bu dosyada ve DB'de tutulur — API response'larına asla eklenmez.
Kaynak: TYF Yelkende Temel Seviye Eğitim Dokümanları + MYK Flask LMS seed_academy.py
"""
import asyncio
import os
import sys

# Doğrudan çalıştırılabilmesi için path düzeltmesi
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.academy import (
    AcademyLesson,
    AcademyLessonStep,
    AcademyModule,
    AcademyProgram,
    AcademyQuizQuestion,
)

# ── Quiz soruları (kaynak: Flask LMS seed_academy.py 'baglar' bölümü) ─────────
# Gerçek sorular — Flask LMS'ten birebir alındı, doğru harf dahil.
# SECURITY: correct_letter yalnızca bu listede ve DB'de bulunur; API response'a EKLENMEz.
IZBARCO_QUIZ = [
    {
        "sira": 1,
        "soru_metni": "İzbarço bağının en önemli özelliği nedir?",
        "options": [
            {"harf": "A", "metin": "İki ipi birleştirir"},
            {"harf": "B", "metin": "İlmek boyutu sabit kalır ve kolayca çözülür"},
            {"harf": "C", "metin": "Halatın ucunu keser"},
            {"harf": "D", "metin": "Yalnızca kalın halatlarda kullanılır"},
        ],
        "correct_letter": "B",
        "aciklama": "İzbarço bağında ilmek boyutu sabit kalır ve sıkışmadan kolayca çözülür. Yelkenciliğin en sık kullanılan bağıdır.",
    },
    {
        "sira": 2,
        "soru_metni": "Hangi bağ yelkencilikte en sık kullanılır?",
        "options": [
            {"harf": "A", "metin": "Camadan"},
            {"harf": "B", "metin": "Kropi (sekiz)"},
            {"harf": "C", "metin": "Kazık"},
            {"harf": "D", "metin": "İzbarço"},
        ],
        "correct_letter": "D",
        "aciklama": "İzbarço bağı yelkencilikte en sık kullanılan bağdır.",
    },
    {
        "sira": 3,
        "soru_metni": "Kropi (sekiz) bağı ne amaçla kullanılır?",
        "options": [
            {"harf": "A", "metin": "İki ipi birleştirmek için"},
            {"harf": "B", "metin": "Halatın ucunun bloktan kaçmasını önlemek için"},
            {"harf": "C", "metin": "Tekneyi direğe bağlamak için"},
            {"harf": "D", "metin": "Yelkeni direğe bağlamak için"},
        ],
        "correct_letter": "B",
        "aciklama": "Kropi (sekiz bağı), halatın ucunun makara veya bloktan kaçmasını önler.",
    },
    {
        "sira": 4,
        "soru_metni": "Hangi bağ eşit çaplı iki ipi birbirine bağlamak için kullanılır?",
        "options": [
            {"harf": "A", "metin": "Kazık bağı"},
            {"harf": "B", "metin": "İzbarço"},
            {"harf": "C", "metin": "Camadan bağı"},
            {"harf": "D", "metin": "Kropi (sekiz)"},
        ],
        "correct_letter": "C",
        "aciklama": "Camadan bağı, eşit çaplı iki ipi birleştirmek için kullanılan bağdır.",
    },
    {
        "sira": 5,
        "soru_metni": "Teknenin baş ipini bir direğe bağlamak için hangi bağ kullanılır?",
        "options": [
            {"harf": "A", "metin": "Camadan bağı"},
            {"harf": "B", "metin": "Kropi (sekiz)"},
            {"harf": "C", "metin": "Kazık bağı"},
            {"harf": "D", "metin": "İzbarço"},
        ],
        "correct_letter": "C",
        "aciklama": "Kazık bağı, teknenin baş ipini bir direğe bağlamak için kullanılır.",
    },
]


async def seed(db: AsyncSession) -> dict:
    """Seed verisini yükle; mevcut kayıtlar atlanır (idempotent)."""
    stats: dict = {"created": 0, "skipped": 0}

    def _created(label: str) -> None:
        stats["created"] += 1
        print(f"  [+] {label}")

    def _skipped(label: str) -> None:
        stats["skipped"] += 1
        print(f"  [=] {label} (mevcut)")

    # ── Program ───────────────────────────────────────────────────────────
    result = await db.execute(
        select(AcademyProgram).where(AcademyProgram.slug == "d1")
    )
    program = result.scalar_one_or_none()
    if program is None:
        program = AcademyProgram(
            slug="d1",
            kod="D1",
            ad="Deniz 1 Programı",
            aciklama="Temel denizcilik bilgileri — güvenlik, ekipman, bağlar ve seyir.",
            seviye=1,
            club_id=None,
            aktif=True,
        )
        db.add(program)
        await db.flush()
        _created(f"Program: d1 (id={program.id})")
    else:
        _skipped(f"Program: d1 (id={program.id})")

    # ── Module ────────────────────────────────────────────────────────────
    result = await db.execute(
        select(AcademyModule).where(
            AcademyModule.program_id == program.id,
            AcademyModule.slug == "gemici-baglari",
        )
    )
    module = result.scalar_one_or_none()
    if module is None:
        module = AcademyModule(
            program_id=program.id,
            slug="gemici-baglari",
            ad="Gemici Bağları",
            sira=1,
            aktif=True,
        )
        db.add(module)
        await db.flush()
        _created(f"Modül: gemici-baglari (id={module.id})")
    else:
        _skipped(f"Modül: gemici-baglari (id={module.id})")

    # ── Lesson ────────────────────────────────────────────────────────────
    result = await db.execute(
        select(AcademyLesson).where(AcademyLesson.slug == "izbarco")
    )
    lesson = result.scalar_one_or_none()
    if lesson is None:
        lesson = AcademyLesson(
            module_id=module.id,
            slug="izbarco",
            ad="İzbarço",
            aciklama="Bowline — yelkenciliğin en temel bağı. İlmek boyutu sabit kalır, kolayca çözülür.",
            ders_tipi="knot",
            tahmini_sure_dk=10,
            sira=1,
            aktif=True,
        )
        db.add(lesson)
        await db.flush()
        _created(f"Ders: izbarco (id={lesson.id})")
    else:
        _skipped(f"Ders: izbarco (id={lesson.id})")

    # ── LessonStep ────────────────────────────────────────────────────────
    result = await db.execute(
        select(AcademyLessonStep).where(
            AcademyLessonStep.lesson_id == lesson.id,
            AcademyLessonStep.sira == 1,
        )
    )
    step = result.scalar_one_or_none()
    if step is None:
        step = AcademyLessonStep(
            lesson_id=lesson.id,
            sira=1,
            tip="knot_animation",
            baslik="İzbarço Animasyonu",
            data_json={
                "slug": "izbarco",
                "timeline_url": "/api/v1/academy/knot/izbarco/timeline",
            },
        )
        db.add(step)
        await db.flush()
        _created("Adım: İzbarço Animasyonu (sira=1)")
    else:
        _skipped("Adım: sira=1")

    # ── QuizQuestions ─────────────────────────────────────────────────────
    for q_data in IZBARCO_QUIZ:
        result = await db.execute(
            select(AcademyQuizQuestion).where(
                AcademyQuizQuestion.lesson_id == lesson.id,
                AcademyQuizQuestion.sira == q_data["sira"],
            )
        )
        question = result.scalar_one_or_none()
        if question is None:
            db.add(
                AcademyQuizQuestion(
                    lesson_id=lesson.id,
                    sira=q_data["sira"],
                    soru_metni=q_data["soru_metni"],
                    options=q_data["options"],
                    correct_letter=q_data["correct_letter"],
                    aciklama=q_data["aciklama"],
                )
            )
            _created(f"Soru {q_data['sira']}: {q_data['soru_metni'][:50]}…")
        else:
            _skipped(f"Soru {q_data['sira']}")

    await db.flush()
    return stats


async def main() -> None:
    print("Academy seed başlatılıyor…")
    async with AsyncSessionLocal() as db:
        stats = await seed(db)
        await db.commit()
    print(f"\nSeed tamamlandı — oluşturulan: {stats['created']}, atlanan: {stats['skipped']}")


if __name__ == "__main__":
    asyncio.run(main())
