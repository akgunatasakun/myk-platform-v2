"""Kişi yönetimi API router — CRUD + tenant izolasyonu + RBAC."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_action
from app.core.rbac import SENSITIVE_FIELD_MASK_ROLES, require_permission
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.dependencies.storage import get_storage
from app.models.person import Person, PersonRole
from app.schemas.auth import TokenPayload
from app.schemas.person import PersonCreate, PersonListOut, PersonOut, PersonUpdate
from app.services.storage import ObjectStorageService

AVATAR_URL_EXPIRES = 3600   # 1 saat

router = APIRouter(prefix="/persons", tags=["persons"])


def _should_mask(role: str) -> bool:
    return role in SENSITIVE_FIELD_MASK_ROLES


def _build_person_out(person: Person, mask: bool) -> PersonOut:
    return PersonOut.from_orm_masked(person, mask=mask)


async def _get_person_for_club(
    person_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> Person:
    """club_id WHERE koşuluyla kişiyi yükle; bulunamazsa 404 döndür."""
    result = await db.execute(
        select(Person)
        .options(selectinload(Person.roles))
        .where(
            Person.id == person_id,
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
        )
    )
    person = result.scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kişi bulunamadı.")
    return person


@router.get("", response_model=PersonListOut)
async def list_persons(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    role_code: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:read")),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorageService = Depends(get_storage),
) -> PersonListOut:
    base_query = (
        select(Person)
        .where(Person.club_id == club_id)
        .where(Person.is_deleted.is_(False))
    )

    if search:
        pattern = f"%{search}%"
        base_query = base_query.where(
            Person.first_name.ilike(pattern)
            | Person.last_name.ilike(pattern)
            | Person.email.ilike(pattern)
            | Person.phone.ilike(pattern)
        )

    if role_code is not None:
        # FIX: distinct() ile join'de oluşabilecek çift kayıt önlenir
        base_query = (
            base_query.join(PersonRole, PersonRole.person_id == Person.id)
            .where(PersonRole.role_code == role_code)
            .distinct()
        )

    if is_active is not None:
        base_query = base_query.where(Person.is_active.is_(is_active))

    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        base_query.order_by(Person.last_name, Person.first_name)
        .offset(skip)
        .limit(limit)
    )
    persons = result.scalars().all()

    # N+1 önleme: tüm avatar key'leri tek batch çağrısıyla işle
    avatar_keys = [p.avatar_object_key for p in persons if p.avatar_object_key]
    url_map: dict[str, str] = {}
    if avatar_keys:
        url_map = await storage.presigned_url_batch(avatar_keys, expires=AVATAR_URL_EXPIRES)

    mask = _should_mask(current_user.role)
    items: list[PersonOut] = []
    for p in persons:
        out = _build_person_out(p, mask=mask)
        if p.avatar_object_key and p.avatar_object_key in url_map:
            out.avatar_url = url_map[p.avatar_object_key]
        items.append(out)

    return PersonListOut(items=items, total=total, skip=skip, limit=limit)


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def create_person(
    body: PersonCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:write")),
    db: AsyncSession = Depends(get_db),
) -> PersonOut:
    # Aynı kulüpte e-posta tekrarını kontrol et
    if body.email:
        dup = await db.execute(
            select(Person).where(
                Person.club_id == club_id,
                Person.email == body.email,
                Person.is_deleted.is_(False),
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu e-posta adresi bu kulüpte zaten kayıtlı.",
            )

    person = Person(
        club_id=club_id,
        first_name=body.first_name,
        last_name=body.last_name,
        national_id=body.national_id,
        birth_date=body.birth_date,
        gender=body.gender,
        phone=body.phone,
        email=body.email,
        address=body.address,
        emergency_contact_name=body.emergency_contact_name,
        emergency_contact_phone=body.emergency_contact_phone,
        blood_type=body.blood_type,
        notes=body.notes,
        # avatar_object_key API üzerinden set edilmez; POST /avatar endpoint'i kullanılır
    )
    db.add(person)
    await db.flush()

    for code in body.role_codes:
        db.add(PersonRole(person_id=person.id, role_code=code))
    await db.flush()

    # selectinload ile ilişkiyi güvenli şekilde yükle
    result = await db.execute(
        select(Person).options(selectinload(Person.roles)).where(Person.id == person.id)
    )
    person = result.scalar_one()

    await log_action(
        db,
        action="person_created",
        resource_type="person",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(person.id),
        after={
            "first_name": person.first_name,
            "last_name": person.last_name,
            "email": person.email,
            "role_codes": body.role_codes,
        },
        request=request,
    )

    mask = _should_mask(current_user.role)
    return _build_person_out(person, mask=mask)


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(
    person_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:read")),
    db: AsyncSession = Depends(get_db),
) -> PersonOut:
    # FIX: club_id WHERE koşulunda — assert_same_club'a gerek yok
    person = await _get_person_for_club(person_id, club_id, db)
    mask = _should_mask(current_user.role)
    return _build_person_out(person, mask=mask)


@router.patch("/{person_id}", response_model=PersonOut)
async def update_person(
    person_id: uuid.UUID,
    body: PersonUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:write")),
    db: AsyncSession = Depends(get_db),
) -> PersonOut:
    # FIX: club_id WHERE koşulunda — assert_same_club'a gerek yok
    person = await _get_person_for_club(person_id, club_id, db)

    # FIX: exclude_unset=True — null-clearing desteklenir (exclude_none değil)
    update_data = body.model_dump(exclude_unset=True, exclude={"role_codes"})

    # FIX: E-posta duplicate kontrolü setattr'dan ÖNCE yapılır
    if "email" in update_data and update_data["email"] != person.email:
        new_email = update_data["email"]
        if new_email is not None:
            dup = await db.execute(
                select(Person).where(
                    Person.club_id == club_id,
                    Person.email == new_email,
                    Person.is_deleted.is_(False),
                    Person.id != person_id,
                )
            )
            if dup.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bu e-posta adresi bu kulüpte zaten kayıtlı.",
                )

    # Audit için before/after topla (national_id hassas — atla)
    before: dict = {}
    after: dict = {}
    for field, value in update_data.items():
        if field == "national_id":
            continue
        old_val = getattr(person, field, None)
        if old_val != value:
            before[field] = str(old_val) if old_val is not None else None
            after[field] = str(value) if value is not None else None

    # FIX: setattr duplicate kontrolünden SONRA yapılır
    for field, value in update_data.items():
        setattr(person, field, value)

    # Rol kodlarını güncelle
    old_role_codes: list[str] = []
    new_role_codes: list[str] = []

    if body.role_codes is not None:
        existing_roles_result = await db.execute(
            select(PersonRole).where(PersonRole.person_id == person_id)
        )
        existing_roles = existing_roles_result.scalars().all()
        old_role_codes = sorted(r.role_code for r in existing_roles)
        for role in existing_roles:
            await db.delete(role)
        await db.flush()
        new_role_codes = sorted(body.role_codes)
        for code in body.role_codes:
            db.add(PersonRole(person_id=person_id, role_code=code))

        # FIX: rol değişiklikleri audit log'a eklenir
        if old_role_codes != new_role_codes:
            before["role_codes"] = old_role_codes
            after["role_codes"] = new_role_codes

    await db.flush()

    # FIX: selectinload ile ilişkiyi güvenli şekilde yeniden yükle
    result = await db.execute(
        select(Person).options(selectinload(Person.roles)).where(Person.id == person.id)
    )
    person = result.scalar_one()

    if before or after:
        await log_action(
            db,
            action="person_updated",
            resource_type="person",
            club_id=club_id,
            user_id=uuid.UUID(current_user.sub),
            resource_id=str(person.id),
            before=before,
            after=after,
            request=request,
        )

    mask = _should_mask(current_user.role)
    return _build_person_out(person, mask=mask)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    # FIX: club_id WHERE koşulunda — assert_same_club'a gerek yok
    person = await _get_person_for_club(person_id, club_id, db)

    person.is_deleted = True
    await db.flush()

    await log_action(
        db,
        action="person_deleted",
        resource_type="person",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(person.id),
        request=request,
    )
