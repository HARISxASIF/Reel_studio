# 🎬 Reel Studio — Comprehensive Project Overview & System Manual

> **Version**: 2.0.0  
> **Last Updated**: November 2026  
> **Repository**: `HARISxASIF/Reel_studio`  
> **Primary Workspace**: `d:\Reel_studio`  

---

## 1. Executive Summary

**Reel Studio** is an autonomous, end-to-end AI video production platform designed to convert long-form gaming streams, podcasts, and recordings into viral, high-conversion **vertical reels (1080×1920)** ready for **YouTube Shorts, Instagram Reels, and TikTok**.

The system handles the entire pipeline:
1. **Ingest**: Direct resumable S3 multipart upload, stream URL import (YouTube, Twitch, Kick), or real-time live stream recording.
2. **Transcription & Romanization**: Word-level speech-to-text with `faster-whisper`, preserving exact timestamps, with automatic conversion of spoken Urdu/Hindi into Latin **Roman Urdu & Hinglish**.
3. **AI Discovery & Scoring**: Deep multimodal evaluation using **Google Gemini 3.5 Flash Lite** (with deterministic heuristic fallback), scoring clips on Hook, Payoff, Clarity, and Entertainment within a flexible **30 to 150-second window**.
4. **Smart Video Framing**: High-quality FFmpeg rendering with 9:16 Center Crop, Fit with Blurred Backdrop, Dynamic Pan Offset, and **Gaming Split-Screen** (Facecam top + Gameplay bottom).
5. **Interactive In-Browser Editor**: Drag-and-drop facecam/gameplay crop adjustments, timeline boundary trimming (30–150s), real-time karaoke subtitle styling, and live 9:16 video preview.
6. **Social Media Auto-Publishing Suite**: Direct 1-click **YouTube OAuth 2.0** channel connection (fetching real channel avatar, name, and handle), Fernet-encrypted token storage, Gemini AI hashtag generation, bulk queue orchestration, and manual TikTok preparation.

---

## 2. System Architecture & Tech Stack

```mermaid
flowchart TD
    subgraph Client ["Frontend (Next.js 14)"]
        UI["Web Dashboard & Ingest"]
        Editor["Interactive Reel Editor"]
        SocialUI["Social Publishing Suite"]
    end

    subgraph Backend ["FastAPI Application (Port 8000)"]
        API["REST Endpoints & Auth"]
        SSRF["SSRF Guard & URL Prober"]
        SocialRouter["OAuth & Publishing Router"]
        Encryption["Fernet AES Encryption"]
    end

    subgraph Workers ["Celery Background Workers"]
        TranscribeWorker["faster-whisper (CTranslate2)"]
        GeminiWorker["Gemini AI Evaluator & Limiter"]
        RenderWorker["FFmpeg Video Engine & ASS Subtitles"]
        PublishWorker["YouTube Data API & Social Uploaders"]
    end

    subgraph StorageServices ["Infrastructure Services"]
        PG[("PostgreSQL 16 Database")]
        Redis[("Redis 7 Cache & Broker")]
        MinIO[("MinIO S3 Object Storage")]
    end

    UI --> API
    Editor --> API
    SocialUI --> API
    API --> PG
    API --> Redis
    API --> MinIO
    Redis --> Workers
    Workers --> MinIO
    Workers --> PG
```

### Technology Matrix

| Subsystem | Technologies & Libraries | Key Responsibilities |
| :--- | :--- | :--- |
| **Frontend Web** | Next.js 14 (App Router), TypeScript, Tailwind CSS, Lucide Icons | Responsive UI, direct S3 multipart uploading, synchronized dual-player video preview, interactive canvas crop manipulation. |
| **API Backend** | FastAPI, Python 3.11, Pydantic v2, SQLAlchemy 2.0 (Asyncpg) | REST endpoints, JWT authentication, presigned URL generation, SSRF security, OAuth callbacks. |
| **Worker Cluster** | Celery 5.4, Redis 7, Python multiprocessing | Distributed, checkpointed background jobs for chunking, transcription, AI evaluation, video rendering, and social posting. |
| **Data Storage** | PostgreSQL 16, Alembic migrations | Relational persistence for users, projects, chunks, candidate reels, social accounts, and publication records. |
| **Object Storage** | MinIO (S3 API compatible) | High-speed storage for source media, chunks, ASS subtitle scripts, and rendered MP4 reels. |
| **Speech-to-Text** | `faster-whisper` (CTranslate2), Whisper Base/Small | Word-level timing extraction, voice activity detection (VAD), multilingual transcription. |
| **AI Evaluation** | Google Gemini 3.5 Flash Lite (`google-genai` SDK) | Viral candidate identification, hook/payoff scoring, Roman Urdu/Hinglish transliteration, hashtag generation. |
| **Video Engine** | FFmpeg 6.x, FFprobe, `libass` | Hardware-accelerated 1080×1920 vertical composition, audio normalization, ASS karaoke subtitle burning. |
| **Security** | Fernet (cryptography package), SSRF IP filtering | Encrypting OAuth refresh/access tokens at rest, blocking internal RFC1918 network access. |

---

## 3. Core Features & Capabilities

### 3.1 Ingest & Media Import
- **Browser-to-S3 Multipart Upload**: Upload 10GB+ video files directly to MinIO in 10MB chunks with pause, resume, progress percentage, and speed tracking.
- **Universal Stream URL Ingest**: Supports YouTube, Twitch VODs/Clips, Kick streams, and direct HTTP/HTTPS video streams.
- **SSRF Network Protection**: Blocks private, loopback, and cloud metadata IP ranges (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, `169.254.169.254`).
- **Live Stream Capture**: Connects to active live streams with a 15-minute continuous rolling buffer, automated segment stitching, and live clipping.

### 3.2 Transcription & Multilingual Romanization
- **Word-Level Timing**: Every spoken word receives exact `start` and `end` timestamps.
- **Roman Urdu & Hinglish Transliteration**:
  - Urdu speech spoken in Pakistan/India is automatically converted into clean Latin Roman Urdu (e.g., *"Bohat zabardast gameplay"* instead of Nastaliq script).
  - Preserves exact word-by-word timing synchronization for high-energy karaoke highlights.
- **Silent Video Support**: Detects gameplay highlights without commentary, burning prominent headline hooks without subtitle errors.

### 3.3 AI Highlight Extraction (Gemini 3.5 Flash Lite)
- **Flexible 30s to 150s Duration**:
  - Minimum clip length: **30 seconds**.
  - Maximum clip length: **150 seconds** (2.5 minutes).
- **Evaluation Criteria**:
  - **Hook Score (0–100)**: Evaluates the opening 3–5 seconds for scroll-stopping curiosity.
  - **Payoff Score (0–100)**: Ensures a satisfying punchline, climax, or conclusion.
  - **Clarity Score (0–100)**: Verifies the clip makes complete sense out of context.
  - **Entertainment Score (0–100)**: Measures humor, drama, or skill level.
- **Dynamic Rate Limiter & Cooldown**: Built-in RPM/TPM tracking prevents quota exhaustion on Google AI Studio keys.
- **Heuristic Fallback Engine**: If an API key is omitted or rate-limited, the system uses audio peak energy and speech density to extract clips automatically.

### 3.4 Video Rendering & Framing Modes
1. **Center Crop (9:16)**: Standard vertical crop centered on action.
2. **Fit with Blurred Backdrop**: Scales original 16:9 video in the center with a stylized, Gaussian-blurred copy filling the background.
3. **Manual Pan Offset**: Horizontal offset (-1.0 to +1.0) to focus on off-center action.
4. **Gaming Split-Screen**:
   - **Top Region**: Facecam streamer box with custom crop (`x`, `y`, `width`, `height`).
   - **Bottom Region**: Main gameplay window.
   - **Interactive Drag Adjustment**: Real-time canvas tool in the editor allows drag-to-resize and repositioning of facecam and gameplay boxes.

### 3.5 Karaoke Subtitles & Styling
- **Subtitle Script Generation**: Emits Advanced SubStation Alpha (`.ass`) scripts with primary color, accent highlight color, and word-by-word timing tags (`{\k...}`).
- **Customizable Styling**:
  - Position: Bottom, Middle, or Custom vertical offset (10% to 90%).
  - Fonts: Montserrat, Arial, Impact, Roboto, etc.
  - Sizes: Small (42px), Medium (54px), Large (66px), Extra Large (80px), or custom slider (32–96px).
  - Colors: Primary text color and active word karaoke highlight color.

### 3.6 Social Media Publishing Suite ("Upload on Social Media" Tab)
- **Official 1-Click YouTube OAuth 2.0**:
  - Prominent branded **"Connect YouTube Channel"** button.
  - One-click launch to Google Accounts consent dialog (`https://accounts.google.com/o/oauth2/v2/auth`).
  - Minimum publishing scopes requested: `youtube.upload` and `youtube.readonly`.
  - Callback fetches authenticated channel name, custom handle (`@username`), and profile avatar image via YouTube Data API v3.
  - Persists credentials encrypted with Fernet AES-128.
- **Interactive Multi-Account Selection Bar**:
  - Prominent bar to toggle destination accounts ON or OFF for batch uploads.
  - Per-reel account override toggles in metadata review.
- **Gemini AI Hashtag Suggester**:
  - Analyzes reel title, reason, and transcript snippet.
  - Generates interactive, deduplicated hashtag chips (e.g., `#GTA6`, `#GamingReels`, `#Shorts`).
  - Add, Remove, and Add All actions with character counter limits.
- **Platform-Specific Metadata Formatting**:
  - YouTube: Separate Title and Description with embedded hashtags and tags.
  - Meta/Instagram/TikTok: Combined caption with hook, description, and hashtags.
- **Background Publishing Queue**:
  - Celery background workers process uploads independently.
  - Idempotency protection prevents duplicate uploads on page refreshes or double-clicks.
  - Retry mechanism for failed uploads without re-uploading to successful destinations.
- **TikTok Manual Upload Preparation**:
  - One-click final MP4 download.
  - Automatic caption and hashtag clipboard copy.
  - Direct deep link to TikTok web upload page.

---

## 4. Database Schema Overview

```mermaid
erDiagram
    User ||--o{ Project : owns
    User ||--o{ SocialAccount : connects
    Project ||--o{ ProjectChunk : divides
    Project ||--o{ Reel : produces
    Project ||--o{ SocialPost : publishes
    Reel ||--o{ SocialPost : targets
    SocialAccount ||--o{ SocialPost : receives

    User {
        uuid id PK
        string email
        string hashed_password
        boolean is_active
        datetime created_at
    }

    Project {
        uuid id PK
        uuid user_id FK
        string title
        string source_type
        string status
        float duration
        string source_file_key
        string framing_mode
        json facecam_crop
        json gameplay_crop
    }

    Reel {
        uuid id PK
        uuid project_id FK
        string title
        string top_caption
        float source_start
        float source_end
        float clip_duration
        float score
        string render_status
        string video_key
        json transcript_words
        json ass_script
    }

    SocialAccount {
        uuid id PK
        uuid user_id FK
        string platform
        string account_name
        string account_username
        string profile_picture_url
        string access_token_encrypted
        string refresh_token_encrypted
        datetime token_expires_at
        string status
        boolean is_active
    }

    SocialPost {
        uuid id PK
        uuid project_id FK
        uuid reel_id FK
        uuid social_account_id FK
        string status
        string post_title
        string post_description
        json hashtags
        string remote_post_id
        string post_url
        string idempotency_key
    }
```

---

## 5. API Endpoint Reference

### 5.1 System & Health
- `GET /api/system/health`: Full health check of Postgres, Redis, MinIO, and Gemini AI.
- `GET /api/system/ai-status`: Gemini configuration state, active model, and setup instructions.

### 5.2 Projects & Ingest
- `POST /api/projects`: Create a new project.
- `GET /api/projects`: List all user projects.
- `GET /api/projects/{id}`: Get project details, chunks, and reels.
- `DELETE /api/projects/{id}`: Delete project and associated S3 assets.
- `POST /api/projects/metadata`: Probe remote video URL (YouTube, Twitch, Kick).
- `POST /api/projects/import-url`: Import media stream from verified URL into storage.
- `POST /api/projects/multipart/create`: Initiate direct S3 multipart upload.
- `POST /api/projects/multipart/sign-part`: Sign an individual 10MB chunk for upload.
- `POST /api/projects/multipart/complete`: Assemble uploaded parts into final source video.
- `POST /api/projects/{id}/start-processing`: Kick off chunking and transcription pipeline.
- `POST /api/projects/{id}/reels/manual`: Create custom reel with 30s–150s boundaries.

### 5.3 Reels & Editor
- `GET /api/reels/{id}`: Get reel details, playback URLs, transcript words, and styling.
- `PATCH /api/reels/{id}`: Update framing mode, facecam crop, subtitle styling, or trim boundaries (30–150s).
- `POST /api/reels/{id}/render`: Queue background FFmpeg render task for approved changes.
- `GET /api/reels/{id}/download`: Get download URL for final vertical MP4.
- `DELETE /api/reels/{id}`: Remove reel.

### 5.4 Social Media Publishing
- `GET /api/social/accounts`: List connected social accounts.
- `GET /api/social/{platform}/authorize`: Generate official OAuth authorization URL.
- `GET /api/social/youtube/callback`: OAuth callback endpoint for YouTube channel authorization.
- `POST /api/social/accounts/disconnect`: Disconnect an account and cancel queued posts.
- `POST /api/social/accounts/reconnect`: Reactivate disconnected account.
- `POST /api/social/hashtags/suggest`: Gemini AI contextual hashtag generator.
- `POST /api/social/publish/batch`: Queue batch reel publishing across selected destination accounts.
- `GET /api/social/posts/project/{projectId}`: List social publication records and live statuses.
- `POST /api/social/posts/{postId}/retry`: Retry a failed social post upload.
- `POST /api/social/tiktok/prepare`: Generate TikTok manual upload bundle (download URL, caption, tags).

---

## 6. Installed Skills & Customizations

Reel Studio includes specialized Antigravity agent skills installed in [`.agents/skills/`](file:///d:/Reel_studio/.agents/skills/):

1. **`ui-ux-pro-max`** ([`.agents/skills/ui-ux-pro-max/SKILL.md`](file:///d:/Reel_studio/.agents/skills/ui-ux-pro-max/SKILL.md)):
   - Design intelligence containing 80 UI styles, 194 color palettes, 74 font pairings, 141 UX/accessibility guidelines, 25 chart types, and 22 technology stacks.
   - Run local search: `python .agents/skills/ui-ux-pro-max/scripts/search.py "gaming reel editor" --design-system`.
2. **`design`** ([`.agents/skills/design/SKILL.md`](file:///d:/Reel_studio/.agents/skills/design/SKILL.md)):
   - Design tokens, logo generation, brand identity guidelines.
3. **`banner-design`** ([`.agents/skills/banner-design/SKILL.md`](file:///d:/Reel_studio/.agents/skills/banner-design/SKILL.md)):
   - Social media banner assets for YouTube, Facebook, and Instagram.
4. **`slides`** ([`.agents/skills/slides/SKILL.md`](file:///d:/Reel_studio/.agents/skills/slides/SKILL.md)):
   - HTML presentations and Chart.js visualizations.
5. **`ui-styling`** ([`.agents/skills/ui-styling/SKILL.md`](file:///d:/Reel_studio/.agents/skills/ui-styling/SKILL.md)):
   - Radix UI + Tailwind CSS styling patterns.

---

## 7. Environment Configuration Reference (`.env`)

```ini
# Application Security
SECRET_KEY=reelstudio_development_secret_key_change_in_production_min32chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/reelstudio
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:postgres@postgres:5432/reelstudio
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=reelstudio

# Redis & Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Storage (MinIO / S3)
MINIO_ENDPOINT=minio:9000
MINIO_PUBLIC_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=reel-studio
MINIO_SECURE=false

# Google Gemini AI
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite

# Faster-Whisper
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# Reel Boundaries
MIN_CLIP_DURATION=30.0
MAX_CLIP_DURATION=150.0

# YouTube Shorts OAuth Credentials
YOUTUBE_CLIENT_ID=your_client_id.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/social/youtube/callback

# Meta (Facebook & Instagram)
META_APP_ID=
META_APP_SECRET=
META_REDIRECT_URI=http://localhost:8000/api/social/meta/callback

# TikTok
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_REDIRECT_URI=http://localhost:8000/api/social/tiktok/callback
```

---

## 8. Development & Operations Guide

### Starting the Stack
```powershell
# From project root: d:\Reel_studio
docker compose up -d
```

### Running Backend Tests
```powershell
docker exec reelstudio-api pytest tests/
```
*(All 35 automated unit and integration tests currently pass cleanly).*

### Restarting Application Services
```powershell
docker compose restart api worker web
```

### Inspecting Container Logs
```powershell
docker logs -f reelstudio-api
docker logs -f reelstudio-worker
docker logs -f reelstudio-web
```

---

## 9. Recent Key Improvements & Milestones

1. **Duration Extended to 30–150s**:
   - Replaced legacy 60s cap with 150s (2.5 min) across config, Gemini prompts, schemas, validators, edit reel trim sliders, and custom clip modals.
2. **YouTube Channel 1-Click OAuth Integration**:
   - Wired user credentials into container environments.
   - Built automatic token exchange, Fernet encryption, and channel profile extraction (avatar, channel title, handle).
   - Removed all mock/test buttons in favor of official OAuth login.
3. **Gaming Split-Screen Interactive Crop**:
   - Added interactive canvas controls to drag and reposition facecam and gameplay framing in the reel editor.
4. **AI Hashtag Generation & Bulk Social Publishing**:
   - Integrated Gemini hashtag recommendations, multi-destination account picker, idempotency keys, and resilient Celery background posting.
5. **Automated Roman Urdu & Hinglish Transliteration**:
   - Added Latin Roman script formatting with strict word-level timing preservation for Pakistani and Indian gaming streams.
