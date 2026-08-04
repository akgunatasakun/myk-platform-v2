# Docker Doğrulama — MYK Platform V2 Aşama 2

**Tarih:** 2026-07-30  
**Durum:** BEKLEMEDE — Sandbox ortamında Docker mevcut değil

---

## Ortam Gerçeği

Bu test raporunun hazırlandığı CI sandbox ortamında Docker kurulu değildir.
`docker` komutu `command not found` döndürmektedir.

Bu bölüm iki parçadan oluşur:
1. Docker olmadan doğrulanabilen bileşenler (kodun düzey kontrolü)
2. Docker ortamında çalıştırılacak komutlar ve beklenen çıktılar

---

## Bölüm 1 — Kod Düzeyinde Doğrulanabilenler

### docker-compose.yml Sözdizimi

`docker-compose.yml` içeriği doğrulandı:

**Servisler:**
- `db`: `postgres:16-alpine`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` env, `healthcheck` (pg_isready), `volumes: postgres_data`
- `redis`: `redis:7-alpine`, `volumes: redis_data`
- `api`: `build: backend/`, `depends_on: db/redis (condition: service_healthy)`, `env_file: backend/.env`
- `frontend`: `build: frontend/`, `volumes: frontend/:/app`, Vite dev server
- `nginx`: `image: nginx:1.27-alpine`, `ports: 80:80`, `depends_on: api/frontend`

**Volumes:** `postgres_data`, `redis_data`, `storage_data`

**Healthcheck örneği (db servisi):**
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
  interval: 5s
  timeout: 5s
  retries: 5
```

`api` servisi `depends_on: condition: service_healthy` kullanıyor — PostgreSQL hazır olmadan başlamaz. ✓

### backend/Dockerfile Doğrulaması

```
FROM python:3.12-slim          ✓
WORKDIR /app                   ✓
RUN apt-get install libpq-dev  ✓ (PostgreSQL client library)
COPY requirements.txt          ✓
RUN pip install -r requirements.txt  ✓
CMD uvicorn app.main:app       ✓
```

### frontend/Dockerfile Doğrulaması

```
FROM node:22-alpine AS builder  ✓
npm ci --ignore-scripts         ✓ (güvenli install)
npm run build                   ✓
FROM nginx:1.27-alpine          ✓ (multi-stage)
COPY dist/ /usr/share/nginx/html ✓
try_files $uri $uri/ /index.html ✓ (SPA routing)
```

### infra/nginx/nginx.conf Doğrulaması

```
add_header X-Frame-Options "SAMEORIGIN"    ✓
add_header X-Content-Type-Options "nosniff" ✓
add_header X-XSS-Protection "1; mode=block" ✓
limit_req_zone (api_limit: 30r/s)          ✓
limit_req_zone (login_limit: 5r/m)         ✓
proxy_pass http://api_backend              ✓
WebSocket upgrade (frontend Vite HMR)      ✓
```

---

## Bölüm 2 — Docker Ortamında Çalıştırılacak Komutlar

### 2.1 docker compose config

```bash
cd myk-platform-v2
docker compose config
```

**Beklenen:** YAML çıktısı, syntax hatası yok.

### 2.2 docker compose build --no-cache

```bash
docker compose build --no-cache 2>&1 | tee docker-build.log
```

**Beklenen:**
```
[+] Building ...
 => [db] FROM postgres:16-alpine
 => [redis] FROM redis:7-alpine
 => [api] FROM python:3.12-slim
 ...
 => [frontend] FROM node:22-alpine
 ...
 => [nginx] FROM nginx:1.27-alpine
Successfully built ...
```

### 2.3 docker compose up -d

```bash
docker compose up -d
```

**Beklenen:**
```
✔ Container myk-platform-v2-db-1       Started
✔ Container myk-platform-v2-redis-1    Started
✔ Container myk-platform-v2-api-1      Started
✔ Container myk-platform-v2-frontend-1 Started
✔ Container myk-platform-v2-nginx-1    Started
```

### 2.4 docker compose ps

```bash
docker compose ps
```

**Beklenen:**
```
NAME                      SERVICE     STATUS     PORTS
myk-platform-v2-db-1      db         running    5432/tcp
myk-platform-v2-redis-1   redis      running    6379/tcp
myk-platform-v2-api-1     api        running    8000/tcp
myk-platform-v2-frontend-1 frontend  running    3000/tcp
myk-platform-v2-nginx-1   nginx      running    0.0.0.0:80->80/tcp
```

### 2.5 Health Kontrolleri

```bash
# Backend health
curl http://localhost/api/v1/health
# Beklenen: {"status":"ok","components":{"postgres":"ok","redis":"ok"}}

# Frontend erişim
curl -s -o /dev/null -w "%{http_code}" http://localhost/
# Beklenen: 200

# PostgreSQL health
docker compose exec db pg_isready -U myk_user -d myk_v2
# Beklenen: localhost:5432 - accepting connections

# Redis ping
docker compose exec redis redis-cli ping
# Beklenen: PONG
```

### 2.6 docker compose logs (kritik satırlar)

```bash
docker compose logs --no-color api | tail -20
```

**Beklenen:**
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Bölüm 3 — Doğrulanamayan ve Ertelenen Maddeler

| Madde | Neden | Hedef Sprint |
|---|---|---|
| `docker compose build` gerçek çıktı | Docker yok | Kullanıcı tarafından çalıştırılacak |
| Container health status | Docker yok | Kullanıcı tarafından çalıştırılacak |
| PostgreSQL TCP bağlantısı | Docker yok | `postgres_e2e_verify.sh` |
| Redis TCP bağlantısı | Docker yok | `postgres_e2e_verify.sh` |
| Nginx proxy çalışması | Docker yok | `postgres_e2e_verify.sh` |
| pgcrypto extension load | Docker yok | Aşama 3 Sprint 3.1 |

---

## Çalıştırma Talimatı

```bash
cd myk-platform-v2

# .env hazırla
cp backend/.env.example backend/.env
# .env içini doldur (JWT_SECRET_KEY, POSTGRES_PASSWORD vb.)

# Tam E2E: build + up + migration + API test
bash postgres_e2e_verify.sh
```

Bu script tüm adımları otomatik olarak çalıştırır ve PASS/FAIL çıktısı verir.
