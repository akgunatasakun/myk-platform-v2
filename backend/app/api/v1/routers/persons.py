"""Kişi yönetimi API router — CRUD + tenant izolasyonu + RBAC."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_action
from app.core.rbac import SENSITIVE_FIELD_MASK_ROLES, require_permission
from app.services.training_scope_service import get_antrenor_enrolled_person_ids
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.dependencies.storage import get_storage
from app.models.person import Person, PersonRole
from app.models.person_guardian import PersonGuardian
from app.schemas.auth import TokenPayload
from app.models.user import User
from app.schemas.person import (
    PersonCreate,
    PersonCreateAccountRequest,
    PersonCreateAccountResponse,
    PersonCreateOut,
    PersonListOut,
    PersonOut,
    PersonUpdate,
)
from app.services.user_account_service import create_user_for_person
from app.schemas.person_guardian import (
    GuardianAthleteOut,
    PersonGuardianCreate,
    PersonGuardianOut,
    PersonGuardianUpdate,
)
from app.services.storage import ObjectStorageService

AVATAR_URL_EXPIRES = 3600   # 1 saat

router = APIRouter(prefix="/persons", tags=["persons"])


def _should_mask(role: str) -> bool:
    return role in SENSITIVE_FIELD_MASK_ROLES


def _build_person_out(person: Person, mask: bool) -> PersonOut:
    return PersonOut.from_orm_masked(person, mask=mask)


# Sprint 2.3: Rol öncelik sıralaması — create_account için en yüksek yetkili rol seçilir
_ROLE_PRIORITY: dict[str, int] = {
    "kulup_yonetici": 5,
    "yonetici":       5,
    "antrenor":       4,
    "veli":           3,
    "uye":            2,
    "sporcu":         1,
    "personel":       1,
    "misafir":        0,
}
# Hesap açılabilir roller (sporcu yalnızsa hesap açılmaz)
_ACCOUNT_ELIGIBLE_ROLES = {"antrenor", "veli", "uye", "yonetici", "kulup_yonetici", "personel"}


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
    limit: int = Query(20, ge=1, le=1000),
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

    # Antrenör scope: yalnızca atandığı eğitimlere kayıtlı kişiler + kendisi
    if current_user.role == "antrenor":
        allowed_ids = await get_antrenor_enrolled_person_ids(
            uuid.UUID(current_user.sub), club_id, db
        )
        base_query = base_query.where(Person.id.in_(allowed_ids))

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


@router.post("", response_model=PersonCreateOut, status_code=status.HTTP_201_CREATED)
async def create_person(
    body: PersonCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:write")),
    db: AsyncSession = Depends(get_db),
) -> PersonCreateOut:
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

    # Sprint 2.3: opsiyonel User hesabı
    temp_password: Optional[str] = None
    warnings: list[str] = []

    if body.create_account:
        eligible = [r for r in body.role_codes if r in _ACCOUNT_ELIGIBLE_ROLES]
        if not person.email:
            warnings.append("Hesap için e-posta zorunludur; hesap oluşturulmadı.")
        elif not eligible:
            warnings.append("Seçili roller için otomatik hesap oluşturma desteklenmiyor (yalnızca sporcu/misafir).")
        else:
            best_role = max(eligible, key=lambda r: _ROLE_PRIORITY.get(r, 0))
            try:
                _user, temp_password = await create_user_for_person(
                    person=person,
                    role_code=best_role,
                    assigner_user_id=uuid.UUID(current_user.sub),
                    assigner_role=current_user.role,
                    db=db,
                )
            except HTTPException as exc:
                warnings.append(f"Hesap oluşturulamadı: {exc.detail}")

    await db.commit()
    await db.refresh(person)
    # roles ilişkisini yeniden yükle
    result2 = await db.execute(
        select(Person).options(selectinload(Person.roles)).where(Person.id == person.id)
    )
    person = result2.scalar_one()

    mask = _should_mask(current_user.role)
    out = PersonCreateOut.from_orm_masked(person, mask=mask)
    out.temp_password = temp_password
    out.warnings = warnings
    return out


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(
    person_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:read")),
    db: AsyncSession = Depends(get_db),
) -> PersonOut:
    person = await _get_person_for_club(person_id, club_id, db)
    # Antrenör scope: yalnızca erişebildiği kişileri görebilir
    if current_user.role == "antrenor":
        allowed_ids = await get_antrenor_enrolled_person_ids(
            uuid.UUID(current_user.sub), club_id, db
        )
        if person_id not in allowed_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu kişiye erişim yetkiniz yok.",
            )
    mask = _should_mask(current_user.role)
    out = _build_person_out(person, mask=mask)

    # Sprint 20: bağlı kullanıcı hesabı bilgisini doldur
    linked = await db.execute(
        select(User).where(
            User.person_id == person.id,
            User.club_id == club_id,
            User.is_deleted.is_(False),
        )
    )
    linked_user = linked.scalar_one_or_none()
    if linked_user:
        out.linked_user_id = linked_user.id
        out.linked_user_email = linked_user.email

    return out


@router.post(
    "/{person_id}/create-account",
    response_model=PersonCreateAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Kişi kaydından kullanıcı hesabı oluştur",
)
async def create_account_for_person(
    person_id: uuid.UUID,
    body: PersonCreateAccountRequest,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kullanici:write")),
    db: AsyncSession = Depends(get_db),
) -> PersonCreateAccountResponse:
    """Mevcut kişi kaydına bağlı bir giriş hesabı açar.

    - E-posta zorunlu (Person.email boşsa 422).
    - role_code: kişinin role_codes listesinden biri olmalı.
    - Aktif hesap zaten varsa 409.
    - Geçici parola bir kez döner (G5).
    """
    person = await _get_person_for_club(person_id, club_id, db)

    # Seçilen rol kişide tanımlı mı?
    person_role_codes = [r.role_code for r in person.roles]
    if body.role_code not in person_role_codes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{body.role_code}' bu kişiye atanmış değil. Kişinin rolleri: {person_role_codes}",
        )

    user, temp_password = await create_user_for_person(
        person=person,
        role_code=body.role_code,
        assigner_user_id=uuid.UUID(current_user.sub),
        assigner_role=current_user.role,
        db=db,
    )

    await db.commit()
    await db.refresh(user)

    await log_action(
        db,
        action="user_created_for_person",
        resource_type="user",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(user.id),
        after={"person_id": str(person.id), "role": user.role},
        request=request,
    )

    return PersonCreateAccountResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        temp_password=temp_password,
    )


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


# ─── Veli-Sporcu ilişki endpoint'leri ────────────────────────────────────────


async def _get_guardian_link(
    link_id: uuid.UUID,
    athlete_person_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> PersonGuardian:
    """Guardian bağlantısını yükle; kulüp ve sporcu uyuşmazsa 404 döndür."""
    result = await db.execute(
        select(PersonGuardian)
        .options(selectinload(PersonGuardian.guardian))
        .where(
            PersonGuardian.id == link_id,
            PersonGuardian.athlete_person_id == athlete_person_id,
            PersonGuardian.club_id == club_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Veli bağlantısı bulunamadı."
        )
    return link


async def _clear_primary_for_athlete(
    athlete_person_id: uuid.UUID,
    club_id: uuid.UUID,
    exclude_id: Optional[uuid.UUID],
    db: AsyncSession,
) -> None:
    """Sporcunun mevcut primary veli bağlantılarını False yap (exclude_id hariç)."""
    stmt = (
        update(PersonGuardian)
        .where(
            PersonGuardian.athlete_person_id == athlete_person_id,
            PersonGuardian.club_id == club_id,
            PersonGuardian.is_primary.is_(True),
        )
        .values(is_primary=False)
    )
    if exclude_id is not None:
        stmt = stmt.where(PersonGuardian.id != exclude_id)
    await db.execute(stmt)


@router.get(
    "/{person_id}/guardians",
    response_model=List[PersonGuardianOut],
    summary="Sporcu velilerini listele",
)
async def list_guardians(
    person_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kisi:read")),
    db: AsyncSession = Depends(get_db),
) -> List[PersonGuardianOut]:
    # Sporcu bu kulübe ait mi?
    await _get_person_for_club(person_id, club_id, db)

    result = await db.execute(
        select(PersonGuardian)
        .options(selectinload(PersonGuardian.guardian))
        .where(
            PersonGuardian.athlete_person_id == person_id,
            PersonGuardian.club_id == club_id,
        )
        .order_by(PersonGuardian.is_primary.desc(), PersonGuardian.created_at)
    )
    links = result.scalars().all()
    return [PersonGuardianOut.model_validate(lnk) for lnk in links]



@router.get(
    "/{person_id}/athletes",
    response_model=List[GuardianAthleteOut],
    summary="Velinin bağlı olduğu sporcuları listele",
)
async def list_guardian_athletes(
    person_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kisi:read")),
    db: AsyncSession = Depends(get_db),
) -> List[GuardianAthleteOut]:
    # Veli kişisi gerçekten bu tenant içinde mevcut mu?
    await _get_person_for_club(person_id, club_id, db)

    result = await db.execute(
        select(PersonGuardian)
        .options(selectinload(PersonGuardian.athlete))
        .where(
            PersonGuardian.guardian_person_id == person_id,
            PersonGuardian.club_id == club_id,
        )
        .order_by(
            PersonGuardian.is_primary.desc(),
            PersonGuardian.created_at,
        )
    )
    links = result.scalars().all()

    return [GuardianAthleteOut.model_validate(link) for link in links]



@router.post(
    "/{person_id}/guardians",
    response_model=PersonGuardianOut,
    status_code=status.HTTP_201_CREATED,
    summary="Sporcu velisi ekle",
)
async def add_guardian(
    person_id: uuid.UUID,
    body: PersonGuardianCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kisi:write")),
    db: AsyncSession = Depends(get_db),
) -> PersonGuardianOut:
    # 1. Sporcu bu kulübe ait mi?
    await _get_person_for_club(person_id, club_id, db)

    # 2. Kendi kendini veli yapamaz
    if body.guardian_person_id == person_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kişi kendini veli olarak atayamaz.",
        )

    # 3. Veli kişisi aynı kulüpte mevcut mu ve silinmemiş mi?
    guardian_person = await db.execute(
        select(Person).where(
            Person.id == body.guardian_person_id,
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
        )
    )
    if guardian_person.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veli olarak atanacak kişi bu kulüpte bulunamadı.",
        )

    # 4. is_primary=True ise mevcut primary bağlantıları temizle
    if body.is_primary:
        await _clear_primary_for_athlete(person_id, club_id, exclude_id=None, db=db)

    # 5. Bağlantı kaydı oluştur
    link = PersonGuardian(
        club_id=club_id,
        athlete_person_id=person_id,
        guardian_person_id=body.guardian_person_id,
        relationship_type=body.relationship_type,
        is_primary=body.is_primary,
        can_pickup=body.can_pickup,
        can_receive_notifications=body.can_receive_notifications,
    )
    db.add(link)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu sporcu için aynı veli zaten kayıtlı.",
        )

    # guardian ilişkisini yükle (eager)
    result = await db.execute(
        select(PersonGuardian)
        .options(selectinload(PersonGuardian.guardian))
        .where(PersonGuardian.id == link.id)
    )
    link = result.scalar_one()

    await log_action(
        db,
        action="guardian_added",
        resource_type="person_guardian",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(link.id),
        after={
            "athlete_person_id": str(person_id),
            "guardian_person_id": str(body.guardian_person_id),
            "relationship_type": body.relationship_type,
            "is_primary": body.is_primary,
        },
        request=request,
    )
    return PersonGuardianOut.model_validate(link)


@router.patch(
    "/{person_id}/guardians/{guardian_id}",
    response_model=PersonGuardianOut,
    summary="Veli bağlantısını güncelle",
)
async def update_guardian(
    person_id: uuid.UUID,
    guardian_id: uuid.UUID,
    body: PersonGuardianUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kisi:write")),
    db: AsyncSession = Depends(get_db),
) -> PersonGuardianOut:
    # Sporcu bu kulübe ait mi?
    await _get_person_for_club(person_id, club_id, db)

    link = await _get_guardian_link(guardian_id, person_id, club_id, db)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        # Değişiklik yok — mevcut kaydı döndür
        return PersonGuardianOut.model_validate(link)

    # is_primary=True atanıyorsa diğerlerini temizle
    if update_data.get("is_primary") is True and not link.is_primary:
        await _clear_primary_for_athlete(
            person_id, club_id, exclude_id=link.id, db=db
        )

    for field, value in update_data.items():
        setattr(link, field, value)

    await db.flush()

    # güncel guardian verisiyle yeniden yükle
    result = await db.execute(
        select(PersonGuardian)
        .options(selectinload(PersonGuardian.guardian))
        .where(PersonGuardian.id == link.id)
    )
    link = result.scalar_one()

    await log_action(
        db,
        action="guardian_updated",
        resource_type="person_guardian",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(link.id),
        after=update_data,
        request=request,
    )
    return PersonGuardianOut.model_validate(link)


@router.delete(
    "/{person_id}/guardians/{guardian_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Veli bağlantısını sil",
)
async def delete_guardian(
    person_id: uuid.UUID,
    guardian_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _perm: None = Depends(require_permission("kisi:write")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    # Sporcu bu kulübe ait mi?
    await _get_person_for_club(person_id, club_id, db)

    link = await _get_guardian_link(guardian_id, person_id, club_id, db)

    await db.delete(link)
    await db.flush()

    await log_action(
        db,
        action="guardian_removed",
        resource_type="person_guardian",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(guardian_id),
        request=request,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
