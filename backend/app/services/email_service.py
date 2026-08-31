"""E-posta gönderim servisi — aiosmtplib tabanlı, async.

Config'de SMTP_HOST boş bırakılırsa e-posta sessizce loglanır (dev/test modu).
Production'da /etc/myk/production.env üzerinden SMTP_ değişkenleri set edilmelidir.

Sprint 13 eki:
  dispatch_domain_event_email()  — DomainEvent'e göre şablon seç ve gönder.
  _build_event_email()           — 7 event tipi için konu + HTML üretir.
"""
from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from app.models.events import DomainEvent

logger = logging.getLogger(__name__)

# aiosmtplib opsiyonel bağımlılık — yoksa log modu
try:
    import aiosmtplib  # type: ignore
    _SMTP_AVAILABLE = True
except ImportError:
    _SMTP_AVAILABLE = False
    logger.warning("aiosmtplib bulunamadı — e-postalar loglanır, gönderilmez.")


async def _send(subject: str, to_email: str, html_body: str) -> None:
    """Düşük seviye gönderici — config'den SMTP ayarlarını okur."""
    from app.config import get_settings
    settings = get_settings()

    if not settings.smtp_host or not _SMTP_AVAILABLE:
        # Dev/test modunda sadece logla
        logger.info(
            "[EMAIL LOG] To=%s Subject=%s (SMTP kapalı veya aiosmtplib yok)",
            to_email, subject,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_address
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        use_tls=settings.smtp_use_tls,
        start_tls=settings.smtp_start_tls,
    )
    logger.info("E-posta gönderildi: To=%s Subject=%s", to_email, subject)


async def send_approval_email(
    to_email: str,
    applicant_name: str,
    member_number: str,
    temp_password: Optional[str],
) -> None:
    """Başvuru onay bildirimi."""
    subject = "Üyelik Başvurunuz Onaylandı — Mersin Yelken Kulübü"

    if temp_password:
        login_section = f"""
        <p>Portala giriş yapabilmek için aşağıdaki geçici şifreyi kullanın.
        İlk girişte yeni bir şifre belirlemeniz gerekecektir.</p>
        <p><strong>E-posta:</strong> {to_email}<br>
        <strong>Geçici Şifre:</strong> <code>{temp_password}</code></p>
        """
    else:
        login_section = "<p>Mevcut kullanıcı hesabınızla portala giriş yapabilirsiniz.</p>"

    html = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <h2 style="color:#1a5276;">Mersin Yelken Kulübü</h2>
      <h3>Üyelik Başvurunuz Onaylandı 🎉</h3>
      <p>Sayın {applicant_name},</p>
      <p>Üyelik başvurunuz incelenmiş ve onaylanmıştır.</p>
      <p><strong>Üye Numaranız:</strong> {member_number}</p>
      {login_section}
      <p>Kulübümüze hoş geldiniz!</p>
      <hr>
      <p style="font-size:12px;color:#666;">
        Mersin Yelken Yat ve Su Sporları Kulübü<br>
        Bu e-posta otomatik olarak gönderilmiştir.
      </p>
    </body>
    </html>
    """
    await _send(subject, to_email, html)


async def send_rejection_email(
    to_email: str,
    applicant_name: str,
    reason: Optional[str],
) -> None:
    """Başvuru red bildirimi."""
    subject = "Üyelik Başvurunuz Hakkında — Mersin Yelken Kulübü"

    reason_section = ""
    if reason:
        reason_section = f"<p><strong>Gerekçe:</strong> {reason}</p>"

    html = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <h2 style="color:#1a5276;">Mersin Yelken Kulübü</h2>
      <h3>Üyelik Başvurusu Hakkında</h3>
      <p>Sayın {applicant_name},</p>
      <p>Üyelik başvurunuz incelenmiş ancak bu aşamada kabul edilememiştir.</p>
      {reason_section}
      <p>Daha fazla bilgi için kulüpümüzle iletişime geçebilirsiniz.</p>
      <hr>
      <p style="font-size:12px;color:#666;">
        Mersin Yelken Yat ve Su Sporları Kulübü<br>
        Bu e-posta otomatik olarak gönderilmiştir.
      </p>
    </body>
    </html>
    """
    await _send(subject, to_email, html)


async def send_course_approval_email(
    to_email: str,
    applicant_name: str,
) -> None:
    """Kurs başvurusu onay bildirimi — üye numarası/şifre içermez."""
    subject = "Kurs Başvurunuz Onaylandı — Mersin Yelken Kulübü"
    html = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <h2 style="color:#1a5276;">Mersin Yelken Kulübü</h2>
      <h3>Kurs Başvurunuz Onaylandı</h3>
      <p>Sayın {applicant_name},</p>
      <p>Kurs başvurunuz incelenmiş ve onaylanmıştır.</p>
      <p>Eğitim programı ve başlangıç tarihi hakkında yakında bilgilendirileceksiniz.</p>
      <p>Kulübümüze hoş geldiniz!</p>
      <hr>
      <p style="font-size:12px;color:#666;">
        Mersin Yelken Yat ve Su Sporları Kulübü<br>
        Bu e-posta otomatik olarak gönderilmiştir.
      </p>
    </body>
    </html>
    """
    await _send(subject, to_email, html)


async def send_course_rejection_email(
    to_email: str,
    applicant_name: str,
    reason: Optional[str],
) -> None:
    """Kurs başvurusu red bildirimi."""
    subject = "Kurs Başvurunuz Hakkında — Mersin Yelken Kulübü"
    reason_section = ""
    if reason:
        reason_section = f"<p><strong>Gerekçe:</strong> {reason}</p>"
    html = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <h2 style="color:#1a5276;">Mersin Yelken Kulübü</h2>
      <h3>Kurs Başvurunuz Hakkında</h3>
      <p>Sayın {applicant_name},</p>
      <p>Kurs başvurunuz incelenmiş ancak bu aşamada kabul edilememiştir.</p>
      {reason_section}
      <p>Daha fazla bilgi için kulüpümüzle iletişime geçebilirsiniz.</p>
      <hr>
      <p style="font-size:12px;color:#666;">
        Mersin Yelken Yat ve Su Sporları Kulübü<br>
        Bu e-posta otomatik olarak gönderilmiştir.
      </p>
    </body>
    </html>
    """
    await _send(subject, to_email, html)


async def send_password_reset_email(
    to_email: str,
    reset_url: str,
) -> None:
    """Şifre sıfırlama bağlantısı."""
    subject = "Şifre Sıfırlama — Mersin Yelken Kulübü"
    html = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <h2 style="color:#1a5276;">Mersin Yelken Kulübü</h2>
      <h3>Şifre Sıfırlama</h3>
      <p>Şifrenizi sıfırlamak için aşağıdaki bağlantıya tıklayın.</p>
      <p>Bu bağlantı <strong>1 saat</strong> geçerlidir.</p>
      <p><a href="{reset_url}" style="background:#1a5276;color:white;padding:10px 20px;
         text-decoration:none;border-radius:4px;">Şifremi Sıfırla</a></p>
      <p>Bu isteği siz yapmadıysanız bu e-postayı dikkate almayın.</p>
      <hr>
      <p style="font-size:12px;color:#666;">
        Mersin Yelken Yat ve Su Sporları Kulübü
      </p>
    </body>
    </html>
    """
    await _send(subject, to_email, html)


# ── Domain Event Dispatch (Sprint 13) ─────────────────────────────────────────

# Ortak e-posta şablonu kapsayıcısı
_BASE_STYLE = (
    "font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;"
)
_HEADER = '<h2 style="color:#1a5276;">Mersin Yelken Kulübü</h2>'
_FOOTER = (
    '<hr><p style="font-size:12px;color:#666;">'
    "Mersin Yelken Yat ve Su Sporları Kulübü<br>"
    "Bu e-posta otomatik olarak gönderilmiştir.</p>"
)


def _wrap(body: str) -> str:
    return (
        f'<!DOCTYPE html><html lang="tr">'
        f'<body style="{_BASE_STYLE}">'
        f"{_HEADER}{body}{_FOOTER}"
        f"</body></html>"
    )


def _days_badge(days: int) -> str:
    if days < 0:
        color = "#c0392b"
        text = f"{abs(days)} gün geçti"
    elif days == 0:
        color = "#c0392b"
        text = "Bugün!"
    elif days <= 7:
        color = "#e67e22"
        text = f"{days} gün kaldı"
    else:
        color = "#f39c12"
        text = f"{days} gün kaldı"
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-weight:bold;">{text}</span>'
    )


def _build_event_email(event: "DomainEvent") -> Tuple[str, str]:
    """Event tipine göre (konu, html) döndürür.

    Bilinmeyen event tipi için genel şablon kullanılır.
    """
    p: dict = event.payload or {}
    et = event.event_type

    # ── application.submitted ──────────────────────────────────────────────
    if et == "application.submitted":
        first_name = p.get("first_name", "")
        last_name = p.get("last_name", "")
        app_number = p.get("application_number", "—")
        app_type = p.get("application_type", "membership")
        full_name = f"{first_name} {last_name}".strip() or "—"
        if app_type == "course":
            subject = f"Yeni Kurs Başvurusu — {full_name}"
            body = (
                f"<h3>Yeni Kurs Başvurusu</h3>"
                f"<p>Online kurs başvuru formu aracılığıyla yeni bir başvuru alındı.</p>"
                f"<table style='border-collapse:collapse;width:100%;'>"
                f"<tr><td style='padding:6px;font-weight:bold;'>Ad Soyad</td>"
                f"<td style='padding:6px;'>{full_name}</td></tr>"
                f"<tr><td style='padding:6px;font-weight:bold;'>Başvuru No</td>"
                f"<td style='padding:6px;'>{app_number}</td></tr>"
                f"<tr><td style='padding:6px;font-weight:bold;'>Tür</td>"
                f"<td style='padding:6px;'>Kurs Başvurusu</td></tr>"
                f"</table>"
            )
        else:
            subject = f"Yeni Üyelik Başvurusu — {full_name}"
            body = (
                f"<h3>Yeni Üyelik Başvurusu</h3>"
                f"<p>Online üyelik başvuru formu aracılığıyla yeni bir başvuru alındı.</p>"
                f"<table style='border-collapse:collapse;width:100%;'>"
                f"<tr><td style='padding:6px;font-weight:bold;'>Ad Soyad</td>"
                f"<td style='padding:6px;'>{full_name}</td></tr>"
                f"<tr><td style='padding:6px;font-weight:bold;'>Başvuru No</td>"
                f"<td style='padding:6px;'>{app_number}</td></tr>"
                f"<tr><td style='padding:6px;font-weight:bold;'>Tür</td>"
                f"<td style='padding:6px;'>Üyelik Başvurusu</td></tr>"
                f"</table>"
            )
        return subject, _wrap(body)

    # ── payment.overdue ────────────────────────────────────────────────────
    if et == "payment.overdue":
        due = p.get("due_date", "—")
        amount = p.get("amount", "—")
        ptype = p.get("payment_type", "")
        subject = f"⚠️ Gecikmiş Ödeme — {due}"
        body = (
            f"<h3>Gecikmiş Ödeme Uyarısı</h3>"
            f"<p>Aşağıdaki ödeme vadesi geçmiş durumda:</p>"
            f"<table style='border-collapse:collapse;width:100%;'>"
            f"<tr><td style='padding:6px;font-weight:bold;'>Tutar</td>"
            f"<td style='padding:6px;'>{amount} TL</td></tr>"
            f"<tr><td style='padding:6px;font-weight:bold;'>Vade Tarihi</td>"
            f"<td style='padding:6px;'>{due}</td></tr>"
            f"<tr><td style='padding:6px;font-weight:bold;'>Tür</td>"
            f"<td style='padding:6px;'>{ptype}</td></tr>"
            f"</table>"
        )
        return subject, _wrap(body)

    # ── equipment.maintenance.due ──────────────────────────────────────────
    if et == "equipment.maintenance.due":
        name = p.get("name", "—")
        mdate = p.get("next_maintenance_date", "—")
        days = p.get("days_remaining", 0)
        subject = f"🔧 Bakım Zamanı — {name}"
        body = (
            f"<h3>Ekipman Bakım Hatırlatması</h3>"
            f"<p><strong>{name}</strong> için bakım tarihi yaklaşıyor. "
            f"{_days_badge(days)}</p>"
            f"<p><strong>Planlanan Bakım Tarihi:</strong> {mdate}</p>"
        )
        return subject, _wrap(body)

    # ── equipment.insurance.expiring_soon ─────────────────────────────────
    if et == "equipment.insurance.expiring_soon":
        name = p.get("name", "—")
        edate = p.get("insurance_expiry_date", "—")
        days = p.get("days_remaining", 0)
        subject = f"📋 Sigorta Bitiyor — {name}"
        body = (
            f"<h3>Ekipman Sigorta Bitiş Uyarısı</h3>"
            f"<p><strong>{name}</strong> sigortası bitiyor. "
            f"{_days_badge(days)}</p>"
            f"<p><strong>Sigorta Bitiş Tarihi:</strong> {edate}</p>"
        )
        return subject, _wrap(body)

    # ── athlete.license.expiring_soon ─────────────────────────────────────
    if et == "athlete.license.expiring_soon":
        edate = p.get("expiry_date", "—")
        days = p.get("days_remaining", 0)
        subject = f"🏅 Sporcu Lisansı Bitiyor — {edate}"
        body = (
            f"<h3>Sporcu Lisansı Bitiş Uyarısı</h3>"
            f"<p>Bir sporcunun lisansı bitiyor. {_days_badge(days)}</p>"
            f"<p><strong>Bitiş Tarihi:</strong> {edate}</p>"
        )
        return subject, _wrap(body)

    # ── athlete.visa.expiring_soon ────────────────────────────────────────
    if et == "athlete.visa.expiring_soon":
        edate = p.get("expiry_date", "—")
        days = p.get("days_remaining", 0)
        subject = f"🛂 Sporcu Vizesi Bitiyor — {edate}"
        body = (
            f"<h3>Sporcu Vize Bitiş Uyarısı</h3>"
            f"<p>Bir sporcunun vizesi bitiyor. {_days_badge(days)}</p>"
            f"<p><strong>Bitiş Tarihi:</strong> {edate}</p>"
        )
        return subject, _wrap(body)

    # ── athlete.health_report.expiring_soon ───────────────────────────────
    if et == "athlete.health_report.expiring_soon":
        edate = p.get("expiry_date", "—")
        days = p.get("days_remaining", 0)
        subject = f"🏥 Sağlık Raporu Bitiyor — {edate}"
        body = (
            f"<h3>Sporcu Sağlık Raporu Bitiş Uyarısı</h3>"
            f"<p>Bir sporcunun sağlık raporu bitiyor. {_days_badge(days)}</p>"
            f"<p><strong>Bitiş Tarihi:</strong> {edate}</p>"
        )
        return subject, _wrap(body)

    # ── training.session.starts_tomorrow ──────────────────────────────────
    if et == "training.session.starts_tomorrow":
        course = p.get("course_name", "—")
        sdate = p.get("session_date", "—")
        stime = p.get("start_time", "")
        time_str = f" — {stime}" if stime else ""
        subject = f"📚 Yarın Eğitim Var — {course}"
        body = (
            f"<h3>Yarınki Eğitim Hatırlatması</h3>"
            f"<p><strong>{course}</strong> eğitim oturumu yarın gerçekleşiyor.</p>"
            f"<p><strong>Tarih:</strong> {sdate}{time_str}</p>"
        )
        return subject, _wrap(body)

    # ── payment.created ───────────────────────────────────────────────────
    if et == "payment.created":
        amount = p.get("amount", "—")
        ptype = p.get("payment_type", "")
        pmethod = p.get("payment_method", "")
        pstatus = p.get("status", "pending")
        status_tr = "Ödendi" if pstatus == "paid" else "Bekliyor"
        type_row = f"<tr><td style='padding:6px;font-weight:bold;'>Tür</td><td style='padding:6px;'>{ptype}</td></tr>" if ptype else ""
        method_row = f"<tr><td style='padding:6px;font-weight:bold;'>Yöntem</td><td style='padding:6px;'>{pmethod}</td></tr>" if pmethod else ""
        subject = "💳 Yeni Ödeme Kaydedildi"
        body = (
            f"<h3>Ödeme Kaydı</h3>"
            f"<p>Sisteme yeni bir ödeme kaydı eklendi.</p>"
            f"<table style='border-collapse:collapse;width:100%;'>"
            f"<tr><td style='padding:6px;font-weight:bold;'>Tutar</td>"
            f"<td style='padding:6px;'>{amount} TL</td></tr>"
            f"{type_row}{method_row}"
            f"<tr><td style='padding:6px;font-weight:bold;'>Durum</td>"
            f"<td style='padding:6px;'>{status_tr}</td></tr>"
            f"</table>"
        )
        return subject, _wrap(body)

    # ── training.session.created ──────────────────────────────────────────
    if et == "training.session.created":
        course = p.get("course_name", "—")
        sdate = p.get("session_date", "—")
        stime = p.get("start_time", "")
        etime = p.get("end_time", "")
        instructor = p.get("instructor_name", "")
        time_range = ""
        if stime and etime:
            time_range = f" {stime} – {etime}"
        elif stime:
            time_range = f" {stime}"
        instructor_row = (
            f"<tr><td style='padding:6px;font-weight:bold;'>Eğitmen</td>"
            f"<td style='padding:6px;'>{instructor}</td></tr>"
        ) if instructor else ""
        subject = f"🗓️ Yeni Oturum Eklendi — {course}"
        body = (
            f"<h3>Yeni Eğitim Oturumu</h3>"
            f"<p><strong>{course}</strong> kursuna yeni bir oturum eklendi.</p>"
            f"<table style='border-collapse:collapse;width:100%;'>"
            f"<tr><td style='padding:6px;font-weight:bold;'>Tarih</td>"
            f"<td style='padding:6px;'>{sdate}{time_range}</td></tr>"
            f"{instructor_row}"
            f"</table>"
        )
        return subject, _wrap(body)

    # ── Genel / bilinmeyen event tipi ─────────────────────────────────────
    subject = f"MYK Bildirim — {et}"
    body = (
        f"<h3>Platform Bildirimi</h3>"
        f"<p>Yeni bir sistem olayı oluştu: <strong>{et}</strong></p>"
        f"<p>Detaylar için yönetim paneline giriş yapın.</p>"
    )
    return subject, _wrap(body)


async def dispatch_domain_event_email(
    event: "DomainEvent",
    to_email: str,
) -> None:
    """DomainEvent'e göre şablonu seç, alıcıya gönder.

    SMTP kapalıysa (smtp_host boş) _send() sessizce loglar — hata fırlatmaz.
    """
    subject, html = _build_event_email(event)
    await _send(subject, to_email, html)
