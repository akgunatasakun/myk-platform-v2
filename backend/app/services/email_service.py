"""E-posta gönderim servisi — aiosmtplib tabanlı, async.

Config'de SMTP_HOST boş bırakılırsa e-posta sessizce loglanır (dev/test modu).
Production'da /etc/myk/production.env üzerinden SMTP_ değişkenleri set edilmelidir.
"""
from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

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
