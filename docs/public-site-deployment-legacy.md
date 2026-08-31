# mersinyelken.org.tr — Deployment Rehberi
**Hazırlanma tarihi:** 2026-07-23  
**Mimari:** Subdomain (panel.mersinyelken.org.tr)

---

## Site Mimarisi

```
mersinyelken.org.tr          → Statik web sitesi (index.html)
www.mersinyelken.org.tr      → mersinyelken.org.tr'ye yönlendirme
panel.mersinyelken.org.tr    → MYK RC1 yönetim paneli (Flask/Gunicorn)
```

---

## Önerilen Hosting Çözümü

### Hetzner Cloud CX22 — Aylık ~€4.5

| Özellik | Değer |
|---------|-------|
| CPU | 2 vCPU |
| RAM | 4 GB |
| Disk | 40 GB SSD |
| Trafik | 20 TB/ay |
| Aylık ücret | ~€4.5 (~160 ₺) |
| Lokasyon | Frankfurt (Türkiye için önerilen) |
| İşletim sistemi | **Ubuntu 24.04 LTS** |

**Alternatif:** DigitalOcean Droplet Basic ($6/ay) — benzer özellikler.

---

## Adım Adım Kurulum

### 1. Sunucu Al

1. [hetzner.com/cloud](https://hetzner.com/cloud) → Hesap aç
2. "Add Server" → Location: Frankfurt → Image: **Ubuntu 24.04 LTS** → Type: CX22
3. SSH Key ekle:

```bash
ssh-keygen -t ed25519 -C "mersinyelken"
cat ~/.ssh/id_ed25519.pub  # Hetzner'e yapıştır
```

4. Server IP adresini not al (örn: `65.21.xxx.xxx`)

---

### 2. DNS Ayarları

Alan adı sağlayıcınızda şu kayıtları ekle:

```dns
A    @          65.21.xxx.xxx     (mersinyelken.org.tr)
A    www        65.21.xxx.xxx     (www.mersinyelken.org.tr)
A    panel      65.21.xxx.xxx     (panel.mersinyelken.org.tr)
```

DNS yayılması 1–24 saat sürebilir.

---

### 3. Sunucuyu Hazırla

```bash
ssh root@65.21.xxx.xxx

# Güncelleme
apt update && apt upgrade -y

# Temel araçlar
apt install -y curl wget git ufw fail2ban logrotate

# Python + Nginx + Certbot
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# PostgreSQL (Ubuntu 24.04 varsayılan deposundaki sürüm — genellikle 16)
# Belirli bir sürüm garantisi için: https://www.postgresql.org/download/linux/ubuntu/
apt install -y postgresql postgresql-contrib

# Redis
apt install -y redis-server

# Güvenlik duvarı
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable

# Fail2ban başlat
systemctl enable fail2ban
systemctl start fail2ban
```

---

### 4. Web Sitesi Dosyasını Yükle

```bash
# Bilgisayarınızdan:
scp index.html root@65.21.xxx.xxx:/tmp/

# Sunucuda:
mkdir -p /var/www/mersinyelken
cp /tmp/index.html /var/www/mersinyelken/
chown -R www-data:www-data /var/www/mersinyelken
```

---

### 5. Nginx Yapılandırması

#### 5a. Ana Site (mersinyelken.org.tr)

```bash
nano /etc/nginx/sites-available/mersinyelken
```

```nginx
# www → apex yönlendirmesi (ayrı server bloğu — daha temiz)
server {
    listen 80;
    server_name www.mersinyelken.org.tr;
    return 301 https://mersinyelken.org.tr$request_uri;
}

# Ana site
server {
    listen 80;
    server_name mersinyelken.org.tr;
    root /var/www/mersinyelken;
    index index.html;

    # Güvenlik başlıkları
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    add_header Permissions-Policy "geolocation=()";

    # Gzip
    gzip on;
    gzip_types text/html text/css application/javascript image/svg+xml;

    location / {
        try_files $uri $uri/ =404;
    }

    # Cache statik dosyalar
    location ~* \.(css|js|png|jpg|ico|svg|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

#### 5b. Panel Subdomain (panel.mersinyelken.org.tr)

```bash
nano /etc/nginx/sites-available/panel-mersinyelken
```

```nginx
server {
    listen 80;
    server_name panel.mersinyelken.org.tr;

    # Güvenlik başlıkları
    add_header X-Frame-Options "DENY";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Gzip
    gzip on;
    gzip_types application/json text/html text/css application/javascript;

    # Yükleme boyutu (belge yükleme için)
    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;

        # Timeout ayarları
        proxy_connect_timeout 30s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    # Statik dosyalar doğrudan sun
    location /static/ {
        alias /opt/myk/static/;
        expires 7d;
        add_header Cache-Control "public";
    }
}
```

```bash
# Her ikisini de aktif et
ln -s /etc/nginx/sites-available/mersinyelken  /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/panel-mersinyelken /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx
```

---

### 6. SSL Sertifikaları (3 domain aynı anda)

```bash
certbot --nginx \
  -d mersinyelken.org.tr \
  -d www.mersinyelken.org.tr \
  -d panel.mersinyelken.org.tr
```

E-posta gir → Şartları kabul et → Tamamlandı!  
Sertifikalar 90 günde bir otomatik yenilenir.

---

### 7. MYK Paneli — Kurulum

#### 7a. PostgreSQL Veritabanı

```bash
sudo -u postgres psql
```

```sql
CREATE USER myk WITH PASSWORD 'güçlü_şifre_buraya';
CREATE DATABASE mykdb OWNER myk;
\q
```

#### 7b. Uygulama Kopyalama

```bash
# MYK_Yazilim klasörünü sunucuya kopyala
scp -r ./MYK_Yazilim root@65.21.xxx.xxx:/opt/myk

# Sunucuda:
cd /opt/myk
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 7c. Ortam Değişkenleri (.env)

```bash
cp .env.example .env
nano .env
```

```env
SECRET_KEY=çok_uzun_ve_rastgele_bir_değer
JWT_SECRET_KEY=başka_bir_çok_uzun_rastgele_değer
MYK_DB_PATH=postgresql+psycopg2://myk:güçlü_şifre@localhost/mykdb
REDIS_URL=redis://localhost:6379/0
FLASK_ENV=production
```

#### 7d. Migration

```bash
cd /opt/myk
source venv/bin/activate
alembic upgrade head
```

#### 7e. Systemd Servisi

```bash
nano /etc/systemd/system/myk.service
```

```ini
[Unit]
Description=MYK Yelken Yönetim Paneli
After=network.target postgresql.service redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/myk
Environment="PATH=/opt/myk/venv/bin"
EnvironmentFile=/opt/myk/.env
ExecStart=/opt/myk/venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:8000 \
    --timeout 60 \
    --access-logfile /var/log/myk/access.log \
    --error-logfile /var/log/myk/error.log \
    app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
mkdir -p /var/log/myk
chown -R www-data:www-data /var/log/myk /opt/myk

systemctl daemon-reload
systemctl enable myk
systemctl start myk
systemctl status myk   # active (running) görmeli
```

---

### 8. Logrotate

```bash
nano /etc/logrotate.d/myk
```

```
/var/log/myk/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    sharedscripts
    postrotate
        systemctl kill -s USR1 myk
    endscript
}
```

---

### 9. Otomatik Yedekleme

```bash
nano /opt/backup-myk.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M)
DEST=/var/backups/myk

mkdir -p $DEST
# PostgreSQL dump
sudo -u postgres pg_dump mykdb | gzip > $DEST/db_$DATE.sql.gz
# 30 günden eski yedekleri sil
find $DEST -name "*.gz" -mtime +30 -delete
```

```bash
chmod +x /opt/backup-myk.sh
# Her gece 03:00'te çalıştır
echo "0 3 * * * root /opt/backup-myk.sh" >> /etc/crontab
```

> ⚠️ **Kritik:** Yedekler şu an aynı sunucuda tutuluyor. Sunucu kaybında veri de kaybolur.
> Production öncesi aşağıdaki seçeneklerden biriyle **harici yedek** zorunludur.

#### Seçenek A — Hetzner Storage Box (~€3.5/ay)

```bash
# Storage Box erişimi için SSH anahtarı ekle (Hetzner panelinden)
# Ardından backup betiğine şunu ekle:
STORAGE_USER="uXXXXXX"
STORAGE_HOST="${STORAGE_USER}.your-storagebox.de"
rsync -az --delete /var/backups/myk/ \
  ${STORAGE_USER}@${STORAGE_HOST}:/backup/myk/
```

#### Seçenek B — S3 Uyumlu (Cloudflare R2 / Backblaze B2 — ücretsiz katman)

```bash
# AWS CLI veya rclone kur
apt install -y rclone
# rclone yapılandır: rclone config
# Backup betiğine ekle:
rclone copy /var/backups/myk/ remote:myk-backups/
```

Her iki seçenekte de yedek **şifrelenmiş** gönderilmelidir:
```bash
gpg --symmetric --cipher-algo AES256 /var/backups/myk/db_${DATE}.sql.gz
```

---

### 10. Doğrulama

```bash
# Site açılıyor mu?
curl -I https://mersinyelken.org.tr

# Panel erişilebilir mi?
curl -I https://panel.mersinyelken.org.tr

# MYK servisi çalışıyor mu?
systemctl status myk

# SSL geçerli mi?
certbot certificates
```

Tarayıcıda kontrol:

| URL | Beklenen |
|-----|---------|
| `https://mersinyelken.org.tr` | Ana site ✅ |
| `https://www.mersinyelken.org.tr` | Ana siteye yönlendir ✅ |
| `https://panel.mersinyelken.org.tr` | MYK giriş ekranı ✅ |
| Tüm URL'lerde 🔒 | SSL aktif ✅ |

---

## Full Stack Özeti

| Bileşen | Paket | Görev |
|---------|-------|-------|
| Web sunucu | Nginx | Ters proxy + statik dosya |
| Uygulama sunucu | Gunicorn 26 (2 worker) | WSGI gateway |
| Framework | Flask (Python) | MYK RC1 uygulaması |
| Veritabanı | PostgreSQL (Ubuntu 24.04 varsayılanı) | Ana veri (üretim) |
| Cache/Rate limit | Redis | Token + rate limiter |
| Migration | Alembic 0001–0005 | Şema yönetimi |
| SSL | Certbot (Let's Encrypt) | HTTPS (3 domain) |
| Güvenlik duvarı | UFW | 22/80/443 |
| Saldırı önleme | Fail2ban | SSH brute-force koruması |
| Yerel yedek | pg_dump + cron | Günlük otomatik |
| Harici yedek | Hetzner Storage Box / Rclone S3 | Felaket kurtarma |
| Log yönetimi | Logrotate | 30 günlük rotasyon |

---

## Maliyet Özeti

| Kalem | Aylık | Yıllık |
|-------|-------|--------|
| Hetzner CX22 | ~€4.5 | ~€54 |
| SSL Sertifikası | Ücretsiz | Ücretsiz |
| Cloudflare CDN (opsiyonel) | Ücretsiz | Ücretsiz |
| **Toplam** | **~€4.5** | **~€54** |

Alan adı mersinyelken.org.tr ayrıca NIC.tr üzerinden alınır (~500 ₺/yıl).

---

## Not: MYK RC1 Production Durumu

Panel kurulmadan önce şu 3 production engeli kapatılmalıdır:

| ID | Engel | Gereksinim |
|----|-------|-----------|
| OI-08 | Vendor offline bundle | İnternet erişimli makine + `bundle_release.py` |
| OI-14 | PostgreSQL + Redis + Alembic entegrasyon testi | Docker |
| OI-16 | Playwright E2E testleri | Chromium |

Ayrıntı: `/MYK_Yazilim/OPEN_ISSUES.md`
