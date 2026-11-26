# Reel Studio — Production Multi-User SaaS Deployment Guide

This guide details how to deploy **Reel Studio** as a multi-user SaaS so your friends and creators can access it from their browsers on a Vercel-hosted frontend, backed by an always-on Docker host (VPS or cloud server) running FastAPI, Celery workers, PostgreSQL, Redis, and S3-compatible object storage.

---

## Architecture Overview

```
               [ User Browser (Friends' PCs) ]
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │ (Direct multipart uploads
            ▼ (HTTPS / UI)                      ▼  & presigned video stream)
   [ Vercel Edge / CDN ]             [ MinIO / S3 Storage ]
   Next.js 14 Web App                Port 9000 (API) / 9001 (Console)
            │                                   ▲
            ▼ (REST API / JWT)                  │ (Read/Write media)
   [ Docker Host: FastAPI ] ────────────────────┤
   Port 8000 (HTTPS reverse proxy)              │
            │                                   │
            ├──────────────┬────────────────────┤
            ▼              ▼                    ▼
     [ PostgreSQL ]    [ Redis ]       [ Celery Workers ]
       Port 5432       Port 6379        FFmpeg + Whisper + Gemini
```

---

## 1. Vercel Deployment (Frontend)

The Next.js 14 frontend deploys directly to Vercel without requiring node server management.

### Project Settings
- **Framework Preset**: `Next.js`
- **Root Directory**: `frontend`
- **Build Command**: `npm run build`
- **Output Directory**: `.next`
- **Install Command**: `npm install`
- **Node.js Version**: `18.x` or `20.x`

### Environment Variables on Vercel
In the Vercel dashboard under **Project Settings → Environment Variables**, configure:

| Variable | Recommended Value | Purpose |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `https://api.yourdomain.com` | Public HTTPS URL of the FastAPI backend |
| `NEXT_PUBLIC_DEFAULT_MIN_SCORE` | `65` | Default viral score filter for reel candidates |

> **Note**: Do **NOT** set `GEMINI_API_KEY`, `YOUTUBE_CLIENT_SECRET`, or `DATABASE_URL` on Vercel. In SaaS mode, all user credentials are entered securely by each user via the Settings page and encrypted server-side.

---

## 2. Docker Host Deployment (Backend & Workers)

Deploy the backend and background media workers on any Docker-capable server (e.g., Ubuntu VPS, Hetzner, AWS EC2, DigitalOcean) with at least 4 vCPUs, 8 GB RAM, and 50 GB SSD.

### Step 2.1: Clone and Configure Environment

```bash
git clone <your-repo-url> /opt/reelstudio
cd /opt/reelstudio
cp .env.example .env
```

Generate secure production secrets:
```bash
# Generate 64-char SECRET_KEY
openssl rand -hex 32

# Generate Fernet ENCRYPTION_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Configure `.env`:
```ini
# ==========================================
# 1. APPLICATION & CREDENTIAL SECURITY
# ==========================================
SECRET_KEY=<your-generated-secret-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
ENCRYPTION_KEY=<your-generated-fernet-key>
ALLOW_ANONYMOUS_DEV=false
ALLOW_ENV_GEMINI_KEY_FALLBACK=true

# Public URLs
BACKEND_PUBLIC_URL=https://api.yourdomain.com
FRONTEND_PUBLIC_URL=https://reelstudio.vercel.app

# ==========================================
# 2. DATABASE & REDIS
# ==========================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<strong-postgres-password>
POSTGRES_DB=reelstudio
DATABASE_URL=postgresql+asyncpg://postgres:<strong-postgres-password>@postgres:5432/reelstudio
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:<strong-postgres-password>@postgres:5432/reelstudio

REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# ==========================================
# 3. OBJECT STORAGE (MinIO or AWS S3)
# ==========================================
MINIO_ENDPOINT=minio:9000
MINIO_PUBLIC_ENDPOINT=storage.yourdomain.com
MINIO_ACCESS_KEY=<strong-minio-access-key>
MINIO_SECRET_KEY=<strong-minio-secret-key>
MINIO_BUCKET=reel-studio
MINIO_SECURE=true

# ==========================================
# 4. CELERY MEDIA ENGINE
# ==========================================
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_WORKERS=2
CHUNK_DURATION_SECONDS=345
CHUNK_OVERLAP_SECONDS=45
LOG_LEVEL=INFO
```

### Step 2.2: Apply Database Migrations

Run database migrations to ensure all tables, user credentials, and indexes exist:
```bash
docker compose run --rm api alembic upgrade head
```

Verify table ownership status:
```bash
docker compose run --rm api python -m app.scripts.check_ownership --dry-run
```

### Step 2.3: Start Services

```bash
docker compose up -d
```

Verify service health:
```bash
# Check running containers
docker compose ps

# Check API health
curl -f http://localhost:8000/api/health

# Check worker logs
docker compose logs -f worker
```

---

## 3. Reverse Proxy & SSL (Nginx / Caddy / Cloudflare)

Set up Nginx or Caddy on your Docker host with Let's Encrypt SSL:

### Nginx Sample Configuration (`/etc/nginx/sites-available/reelstudio`)
```nginx
# API Backend
server {
    server_name api.yourdomain.com;

    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    listen 443 ssl http2;
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
}

# MinIO Storage (Direct Uploads & Video Streaming)
server {
    server_name storage.yourdomain.com;

    client_max_body_size 5000M;

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    listen 443 ssl http2;
    ssl_certificate /etc/letsencrypt/live/storage.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/storage.yourdomain.com/privkey.pem;
}
```

---

## 4. User Onboarding & Credential Architecture

In SaaS mode, Reel Studio uses a **zero-operator-cost, user-owned credential model**:

### User-Owned Google AI Studio (Gemini)
1. User logs in to their Reel Studio account.
2. User opens **Settings → Integrations → Google AI Studio**.
3. User pastes their personal free API key from [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey).
4. User clicks **Test Connection** & **Save**.
5. Server encrypts the key with AES-256 (Fernet) at rest.
6. All AI jobs initiated by this user (highlight scoring, Hinglish transliteration, hashtag generation) resolve the user's encrypted key. Quota exhaustion on one user's account never degrades service for other users.
7. If a user hasn't configured a key, Reel Studio automatically falls back to **High-Precision Heuristic Mode** (audio amplitude peaks + speech density scoring).

### User-Owned YouTube OAuth Connection
1. User opens **Settings → Integrations → YouTube**.
2. User copies the read-only **Authorized Redirect URI**:
   `https://api.yourdomain.com/api/social/youtube/callback`
3. User enters their own Google Cloud OAuth **Client ID** & **Client Secret** (from their own Google Cloud project with YouTube Data API v3 enabled).
4. User clicks **Connect YouTube Channel** $\rightarrow$ completes Google consent screen.
5. Tokens are encrypted at rest with Fernet and automatically refreshed on 401s using the user's OAuth client.

---

## 5. Backup, Rollback & Disaster Recovery

### PostgreSQL Backup
```bash
# Automated Daily Backup Script
docker exec reelstudio-postgres pg_dump -U postgres reelstudio | gzip > /backups/reelstudio_$(date +%F).sql.gz
```

### PostgreSQL Restore
```bash
gunzip -c /backups/reelstudio_2026-11-26.sql.gz | docker exec -i reelstudio-postgres psql -U postgres -d reelstudio
```

### Database Migration Rollback
```bash
# Roll back last migration
docker exec reelstudio-api alembic downgrade -1

# Roll back to specific revision
docker exec reelstudio-api alembic downgrade <revision_id>
```

---

## 6. Post-Deployment Browser Smoke Test Checklist

Execute this verification checklist once the Vercel site is live:

- [ ] **1. Authentication**:
  - Visit `https://reelstudio.vercel.app/signup`.
  - Create a new account with email/password.
  - Verify redirect to dashboard with personalized greeting and empty workspace action cards.
- [ ] **2. Workspace Isolation**:
  - Verify that no other user's projects or videos are visible.
- [ ] **3. Video Ingest**:
  - Test URL import with a short YouTube / Twitch VOD.
  - Or upload a short MP4 file using the multipart uploader.
  - Verify Celery worker starts chunking and Whisper transcription.
- [ ] **4. Reel Generation & Duration Boundaries**:
  - Open project reels view.
  - Verify generated candidate clips are strictly between **30 and 150 seconds**.
  - Test the reel editor, crop selector (facecam + gameplay split), and subtitle karaoke preview.
- [ ] **5. Settings & Integrations**:
  - Open `/settings`.
  - Enter Gemini API Key $\rightarrow$ click **Test Connection** $\rightarrow$ verify "Connected" status.
  - Verify Authorized Redirect URI displays `https://api.yourdomain.com/api/social/youtube/callback`.
- [ ] **6. Video Download & Storage**:
  - Click **Download MP4** on a completed reel.
  - Verify browser streams or downloads the signed MP4 with 1080×1920 vertical aspect ratio.
