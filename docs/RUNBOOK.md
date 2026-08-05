# MYK Platform V2 — Production Runbook

**Versiyon:** v0.4.0  
**Son güncelleme:** 2026-08-05

Bu belge production deploy, rollback ve acil durum prosedürlerini içerir.

---

## İçindekiler

1. [Normal Deploy Prosedürü](#1-normal-deploy-prosedürü)
2. [Uygulama Rollback](#2-uygulama-rollback)
3. [Veritabanı Rollback (pg_dump restore)](#3-veritabanı-rollback)
4. [MinIO / Dosya Rollback](#4-minio--dosya-rollback)
5. [Servis Yönetimi](#5-servis-yönetimi)
6. [Monitoring ve Log](#6-monitoring-ve-log)
7. [Acil Durum Prosedürleri](#7-acil-durum-prosedürleri)
8. [Bilinen Kısıtlamalar](#8-bilinen-kısıtlamalar)

---

## 1. Normal Deploy Prosedürü

```bash
# Mac'ten çalıştır
bash scripts/deploy_production.sh --tag v0.4.0

# Deploy sonrası smoke test
bash scripts/smoke_test_production.sh
```

Deploy adımları (otomatik):
1. Ön koşul kontrolü (SSH, git temiz ağaç, tag)
2. Sunucu ortam doğrulama (.env, MYK_ENV, ALLOW_PUBLIC_SETUP)
3. PostgreSQL yedeği (pg_dump)
4. MinIO volume yedeği
5. `git checkout <tag>`
6. `docker compose build --no-cache`
7. Altyapı servisleri (db, redis, minio, pdf-service)
8. Alembic migration (`upgrade head`)
9. API + Frontend + Nginx başlat
10. Health check

---

## 2. Uygulama Rollback

Önceki çalışan tag'e (örn. `v0.3.x`) dönmek için:

```bash
ssh myk-server
cd /opt/myk/production/myk-platform-v2

# Önceki tag'e geç
git checkout v0.3.x    # Bilinen son stabil tag

# Yeniden build et
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache

# Servisleri yeniden başlat
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Health kontrol
curl -sf http://localhost/api/v1/health
```

**Uyarı:** Alembic `downgrade` tek başına güvenli değildir. Eğer migration veri dönüştürdüyse, uygulama rollback'i mutlaka veritabanı rollback ile birlikte yapılmalıdır. Aşağıdaki karar ağacını kullan:

```
Migration sadece kolon ekledi (nullable) → downgrade çalışabilir
Migration veri dönüştürdü / kolon kaldırdı → pg_dump restore (Bölüm 3)
```

---

## 3. Veritabanı Rollback

Deploy öncesinde `scripts/deploy_production.sh` otomatik yedek alır:  
`/opt/myk/backups/production-<tarih>/production-db-<tarih>.sql`

**Restore prosedürü:**

```bash
ssh myk-server
cd /opt/myk/production/myk-platform-v2

# Önce servisleri durdur (API — db değil)
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop api frontend nginx

# Yedek dosyasını belirle
BACKUP_FILE="/opt/myk/backups/production-YYYYMMDD_HHMMSS/production-db-YYYYMMDD_HHMMSS.sql"

# DB adı ve kullanıcı (.env'den, terminale basmadan)
DB=$(grep "^POSTGRES_DB=" .env | cut -d= -f2-)
USER=$(grep "^POSTGRES_USER=" .env | cut -d= -f2-)

# Mevcut DB'yi sil ve yeniden oluştur
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  psql -U "${USER}" -c "DROP DATABASE IF EXISTS ${DB};" postgres
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  psql -U "${USER}" -c "CREATE DATABASE ${DB};" postgres

# Yedeği geri yükle
cat "${BACKUP_FILE}" | \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  psql -U "${USER}" "${DB}"

echo "Restore tamamlandı."

# Uygulamayı önceki tag'de başlat (Bölüm 2'yi uygula)
```

**Test (restore sonrası):**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  psql -U "${USER}" -d "${DB}" -tAc "SELECT version_num FROM alembic_version;"
# Beklenen: restore öncesi migration versiyonu
```

---

## 4. MinIO / Dosya Rollback

Deploy sırasında MinIO volume yedeği alınır:  
`/opt/myk/backups/production-<tarih>/minio-data-<tarih>.tar.gz`

**Restore prosedürü:**

```bash
BACKUP_FILE="/opt/myk/backups/production-YYYYMMDD_HHMMSS/minio-data-YYYYMMDD_HHMMSS.tar.gz"

# MinIO container'ı durdur
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop minio

# Volume'u temizle ve geri yükle
docker run --rm \
  -v myk-platform-v2_minio_data:/minio_dst \
  -v "$(dirname "${BACKUP_FILE}"):/backup:ro" \
  alpine sh -c "rm -rf /minio_dst/* && tar -xzf /backup/$(basename "${BACKUP_FILE}") -C /minio_dst"

# MinIO'yu yeniden başlat
docker compose -f docker-compose.yml -f docker-compose.prod.yml start minio
```

**Not:** Dosya restoru nadiren gerekir. Presigned URL'ler ve metadata DB'dedir; MinIO içeriği ikincil kaynaktır.

---

## 5. Servis Yönetimi

```bash
# Durum görüntüle
ssh myk-server "cd /opt/myk/production/myk-platform-v2 && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml ps"

# Tek servisi yeniden başlat (örn. api)
ssh myk-server "cd /opt/myk/production/myk-platform-v2 && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api"

# Tüm servisleri yeniden başlat (volume silmeden)
ssh myk-server "cd /opt/myk/production/myk-platform-v2 && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --force-recreate"

# YASAK: docker compose down -v  →  tüm verileri siler!
```

---

## 6. Monitoring ve Log

```bash
# API logları (son 100 satır, canlı)
ssh myk-server "cd /opt/myk/production/myk-platform-v2 && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=100 api"

# Hata logları
ssh myk-server "cd /opt/myk/production/myk-platform-v2 && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml logs api 2>&1 | grep -i error"

# Nginx erişim logları
ssh myk-server "cd /opt/myk/production/myk-platform-v2 && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml logs nginx"

# PostgreSQL bağlantı sayısı
ssh myk-server "cd /opt/myk/production/myk-platform-v2 && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  psql -U \"\$(grep '^POSTGRES_USER=' .env | cut -d= -f2-)\" \
  -d \"\$(grep '^POSTGRES_DB=' .env | cut -d= -f2-)\" \
  -c 'SELECT count(*) FROM pg_stat_activity;'"
```

---

## 7. Acil Durum Prosedürleri

### API yanıt vermiyor

```bash
ssh myk-server
cd /opt/myk/production/myk-platform-v2

# Önce log bak
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 api

# Container yeniden başlat
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api

# Yeterli değilse uygulama rollback (Bölüm 2)
```

### Veritabanı bağlantı hatası

```bash
# db healthy mi?
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  pg_isready -U "$(grep '^POSTGRES_USER=' .env | cut -d= -f2-)"

# Değilse restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart db
sleep 10
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api
```

### Disk doldu

```bash
# Eski yedekleri temizle (2 haftadan eskiler)
find /opt/myk/backups -maxdepth 1 -type d -mtime +14 -exec rm -rf {} \;

# Docker kullanılmayan image'ları temizle
docker image prune -f

# Log boyutlarını kontrol et
docker system df
```

---

## 8. Bilinen Kısıtlamalar

| Kısıtlama | Durum | Sprint |
|-----------|-------|--------|
| TLS/HTTPS henüz aktif değil | DNS hazır olmadan Certbot çalıştırılamaz | Sprint 4 |
| `myk_app` rolü production'da kullanılmıyor (myk_user kullanılıyor) | Düşük öncelik güvenlik iyileştirmesi | Sprint 4 |
| `init.sql` içinde `myk_app` parolası hardcoded | `02_app_role.sh` ile çözülecek | Sprint 4 |
| Redis auth yok | Tek sunucu ortamında düşük risk | Sprint 4 |
| MinIO external S3'e taşınmadı | Bundled MinIO yeterli | Sprint 4+ |

---

*Bu belge her production deploy sonrasında güncellenmelidir.*
