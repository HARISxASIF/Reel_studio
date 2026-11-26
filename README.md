# 🎬 REEL STUDIO — Automated AI Vertical Video Generator

**Reel Studio** is a full-stack, production-grade web application that converts long video recordings (or URLs from YouTube, Twitch, Kick, and direct video links) into viral, high-energy **30–60 second vertical reels** (1080×1920) formatted for TikTok, Instagram Reels, and YouTube Shorts.

Each reel features:
- **Dedicated Top Region**: Catchy, curiosity-inducing top headline caption that grabs attention in feeds.
- **Center Footage**: Dynamic framing options: **9:16 Center Crop**, **Fit with Blurred Background**, or **Manual Pan Offset**.
- **Dedicated Lower Region**: Precise **word-by-word karaoke highlighted subtitles** synchronized with spoken audio using `faster-whisper` word timestamps.
- **Custom Subtitle Font Resizing**: Select preset font sizes (Small 42px, Medium 54px, Large 66px, Extra Large 80px) or fine-tune with a 32–96px slider with real-time video preview and burned ASS export.
- **English / Roman Script (Roman Urdu & Hinglish)**: Subtitles use the English (Latin) alphabet only. Spoken Urdu is automatically formatted into natural **Roman Urdu** (e.g. *"bohat achha"*, *"kya haal hai"*) and Hindi into **Hinglish** (e.g. *"namaste"*, *"kya baat hai"*) with strict word timing preservation.
- **Silent Clip Support**: Detects high-energy gaming reactions or visual surprises; burns top captions and gracefully omits spoken subtitles.

---

## 🏗️ Architecture & Stack

| Layer | Technology | Details |
|---|---|---|
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind CSS | Direct S3 multipart uploads, live 9:16 preview player, reel editor, subtitle font resizer |
| **Backend API** | FastAPI, Python 3.11, Pydantic v2 | SSRF validation, multipart upload management, JWT auth, presigned URLs, Romanization API |
| **Database** | PostgreSQL 16, SQLAlchemy 2.0, Alembic | Persistent storage for users, projects, chunks, reels, and exports |
| **Broker & Cache** | Redis 7, Celery 5.4 | Bounded worker concurrency, checkpointed stages, idempotent retry |
| **Object Storage** | MinIO (S3-compatible) | Direct browser-to-storage multipart uploads and signed downloads |
| **Media Processing**| FFmpeg & FFprobe, libass | 1080×1920 vertical encoding, ASS karaoke subtitle burning with custom font sizes |
| **Speech-to-Text** | faster-whisper (CTranslate2) | Word-level timestamps, cached models, Urdu/Hindi/English support |
| **AI Evaluation** | Google Gemini API (`gemini-3.5-flash-lite`) | Viral candidate discovery, ranking, Roman Urdu/Hinglish transliteration |

---

## ⚡ Quick Start with Docker (Windows / WSL 2)

### 1. Prerequisites
- **Windows 10/11** with **Docker Desktop** installed and running (WSL 2 backend enabled).
- Git.

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

To enable Gemini AI viral evaluation, edit `.env` and add your Gemini API key:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```
> **Note**: If `GEMINI_API_KEY` is not provided, Reel Studio automatically runs in **High-Precision Heuristic Mode** using audio peak energy and speech density detection, showing a friendly setup banner in the UI so you can test all features immediately without entering a key.

### 3. Start the Application
Run Docker Compose:
```powershell
docker compose up -d --build
```

### 4. Access the Services
- **Website**: [http://localhost:3000](http://localhost:3000)
- **API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **MinIO S3 Console**: [http://localhost:9001](http://localhost:9001) (`minioadmin` / `minioadmin`)
- **MinIO S3 API**: [http://localhost:9000](http://localhost:9000)
- **PostgreSQL**: `localhost:5432` (`postgres` / `postgres`)

---

## 🚀 How to Run Your First Import

### Option A: Upload an Original Video File
1. Open [http://localhost:3000](http://localhost:3000).
2. Drag and drop any video recording (MP4, MKV, MOV, WebM) into the upload area.
3. The browser uploads 10MB parts directly to MinIO storage with real-time byte progress, speed tracking, and pause/resume capability.
4. If an upload is interrupted or you close the browser, reopening the site and re-selecting the file automatically resumes from completed parts.
5. Once uploaded, FFprobe probes tracks and duration, and the analysis pipeline automatically begins.

### Option B: Import from YouTube, Twitch, Kick, or Direct URL
1. Click **Enter Video URL** on the dashboard.
2. Paste any valid link:
   - YouTube: `https://www.youtube.com/watch?v=...`
   - Twitch VOD: `https://www.twitch.tv/videos/...`
   - Kick VOD/Clip: `https://kick.com/...`
   - Direct MP4 stream: `https://.../video.mp4`
3. Reel Studio validates the URL for SSRF security (preventing access to internal networks/private IPs), displays platform metadata, and streams the media into storage.
4. If a URL is restricted or unavailable, the dialog immediately offers **Upload original video** while preserving the source reference.

---

## 🔍 Pipeline Details

### 1. Full-Timeline Chunking & Checkpointing
- The recording is divided into **5 minute 45 second chunks** with **45 seconds of overlap**.
- Timestamps remain source-relative throughout the entire pipeline.
- Word timestamps in the overlap regions are automatically reconciled to prevent duplicate words.
- All chunk states are persisted in PostgreSQL. If a worker is restarted, completed chunks are reused without re-transcribing.

### 2. Multi-Signal Candidate Discovery
- **Speech Density**: High dialogue passages and key quotes.
- **Audio Peaks**: Dynamic energy and volume spikes (e.g. laughter, shouting, excitement).
- **Scene Changes**: Fast visual transitions and camera shifts.
- **Gemini / Heuristic Evaluation**: Scores Hook, Payoff, Standalone Clarity, and Entertainment on a 0–100 scale.
- **No Artificial Reel Limit**: Every moment that satisfies the quality threshold is preserved.

### Option C: Ingest & Auto-Clip from Live Streams (YouTube, Twitch, Kick, Direct HLS)
1. On the project creation dashboard, click **Connect Live Stream**.
2. Enter any supported broadcast link:
   - **Direct HLS Feed**: `https://stream.example.com/live.m3u8`
   - **Twitch Channel**: `https://www.twitch.tv/channel_name`
   - **YouTube Live**: `https://www.youtube.com/watch?v=...`
   - **Kick Stream**: `https://kick.com/...`
3. Reel Studio detects platform stream availability and displays live capability badges:
   - `live_available`: Stream is active and ready for ingestion.
   - `waiting_for_stream`: Streamer is currently offline (waiting for broadcast).
   - `stream_ended`: Stream has completed; prompts attaching VOD/recording.
   - `media_unavailable`: Feed requires login or embed player; offers direct HLS or standard upload.
4. Preview the live edge footage, choose layout (including **Gaming Split Screen** with draggable Facecam & Gameplay crop regions), choose Subtitle Size, and confirm by clicking **Start Live Clipping**.
5. The background worker continuously ingests segments into a rolling buffer, detects stream interruptions/gaps, transcribes speech incrementally with `faster-whisper`, discovers viral moments with Gemini rate limiting, and burns vertical 1080×1920 reels in real time as the broadcast unfolds.
6. Click **Clip Last 60s** at any time to extract and render an instant highlight directly from recent buffer footage.
7. When finished, click **Stop Live Clipping** to drain pending analysis windows while preserving all rendered reels.

---

## 🔍 Pipeline Details

### 1. Full-Timeline Chunking & Checkpointing
- The recording is divided into **5 minute 45 second chunks** with **45 seconds of overlap**.
- Timestamps remain source-relative throughout the entire pipeline.
- Word timestamps in the overlap regions are automatically reconciled to prevent duplicate words.
- All chunk states are persisted in PostgreSQL. If a worker is restarted, completed chunks are reused without re-transcribing.

### 2. Live Stream Buffer & Discontinuity Management
- Bounded rolling buffer on disk (`LIVE_BUFFER_RETENTION_SECONDS=900`, `LIVE_MAX_STORAGE_MB_PER_SESSION=1024`).
- Strict SSRF protection on stream URLs, playlists, variant playlists, HTTP redirects, and individual TS segments.
- Automatic sequence gap tracking records missing intervals in `coverage_gaps` and preserves continuous timeline integrity.
- Independent clip media retention: each generated reel extracts and persists its source footage into MinIO (`reel.source_media_key`), ensuring reels remain editable, previewable, and downloadable long after rolling stream segments expire.

### 3. Distributed AI Rate Limiting (Gemini)
- Shared across live streaming and recorded uploads via Redis.
- Configurable limits: `GEMINI_RPM=15`, `GEMINI_TPM=250000`, `GEMINI_RPD=500`.
- Dynamic HTTP 429 backoff cooldown prevents quota exhaustion while decoupling media capture from AI analysis backlog.

### 4. Multi-Signal Candidate Discovery
- **Speech Density**: High dialogue passages and key quotes.
- **Audio Peaks**: Dynamic energy and volume spikes (e.g. laughter, shouting, excitement).
- **Scene Changes**: Fast visual transitions and camera shifts.
- **Gemini / Heuristic Evaluation**: Scores Hook, Payoff, Standalone Clarity, and Entertainment on a 0–100 scale.
- **No Artificial Reel Limit**: Every moment that satisfies the quality threshold is preserved.

### 5. Interactive Reel Editor & Custom Framing
- **Framing Modes**:
  - `Center Crop`: Vertical 9:16 center crop.
  - `Fit + Blurred BG`: Preserves widescreen 16:9 gameplay or podcasts with blurred video background.
  - `Manual Pan`: Horizontal offset slider (-1.0 to 1.0) to focus on the active speaker.
  - `Gaming Split Screen`: Dual independent crop regions for Facecam and Gameplay with customizable divider position and pane order.
- **Top Caption**: Real-time headline editing.
- **Subtitles**: Word-by-word editor allows fixing typos while maintaining exact word timestamps.
- **Trim Points**: Adjust start and end times with 30–60s duration enforcement.
- **Per-Reel Isolation**: Editing one reel modifies only that reel without affecting project defaults or sibling reels.

### 6. Bulk Export (ZIP Archive)
- Click **Download All as ZIP** on the project page.
- A background worker downloads completed reel MP4s and streams them into a ZIP archive without loading all videos into RAM.
- A presigned download link is generated when ready.

---

## 🧪 Testing and Verification Suites

Run all automated verification suites inside the Docker worker/API containers:

```bash
# 1. Full Unit & Integration Test Suite (27 tests)
docker exec reelstudio-api pytest tests/

# 2. Live Stream Workflow Verification (12-step real HLS server, gaps, rate limiter, dual crop)
docker exec reelstudio-worker python scripts/verify_live_stream.py

# 3. Gaming Split Screen Bug Fix & Crop Framing Verification
docker exec reelstudio-worker python scripts/verify_split_fix.py

# 4. End-to-End Workflow & Settings Snapshot Verification
docker exec reelstudio-worker python scripts/verify_workflow.py

# 5. Social Media Publishing & AI Hashtags Verification
docker exec reelstudio-api python -m app.scripts.verify_social_publishing
```

---

## 📱 Social Media Auto-Publishing Guide

Reel Studio provides a dedicated **"Upload on Social Media"** workspace on every project page to publish rendered vertical exports to **YouTube Shorts**, **Facebook Pages**, **Instagram Professional accounts**, and **TikTok**.

### Features
1. **Multi-Platform Accounts Hub**:
   - Official OAuth 2.0 flows with secure Fernet backend token encryption.
   - Built-in **Test Connect** buttons allow testing the complete publishing flow without waiting for third-party developer app verification.
   - Disconnecting an account automatically halts queued background posts for that destination.
2. **Batch & Multi-Reel Publishing**:
   - Filter and select one, several, or all ready reel exports (`Select All Ready Reels`).
   - Choose global default destinations or override accounts per reel.
   - Snapshot stability: video revision and approved metadata are snapshotted at queue time so later edits do not mutate queued uploads.
3. **AI Hashtags & Brand Tags**:
   - Click **"Suggest Hashtags"** on any reel to query Google Gemini using the reel title, description, and transcript snippet.
   - One-click **+ Add All Suggested**, individual `+` add chips, brand tags, and manual hashtag inputs.
   - Platform limit enforcement (e.g. YouTube 100 character title limit, Instagram 30 tag maximum).
4. **Live Caption Preview**:
   - Per-platform preview tabs (YouTube, Instagram, Facebook, TikTok) showing how title, description, and hashtags combine.
5. **Worker Resilience & Idempotent Deduplication**:
   - Dedicated Celery worker tasks execute uploads in the background.
   - Per-destination retry: failures on one platform do not block or duplicate successful posts to other platforms.
   - Real-time progress tracker with direct links to published reels and individual retry actions.
6. **TikTok Mode Options**:
   - Direct Post API v2 integration with privacy and duet controls.
   - **Prepare for TikTok (Manual Mode)**: 1-click MP4 download, 1-click formatted caption copy, and direct link to open `https://www.tiktok.com/upload`.

---

### 🔑 Developer App Setup & OAuth Configuration

To connect real production accounts, set the following environment variables in your `.env` file:

#### 1. YouTube Shorts (Google Cloud Console)
1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Under **APIs & Services > Library**, enable **YouTube Data API v3**.
3. Under **OAuth consent screen**, configure an External user type, add test user emails, and request scopes:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube.readonly`
4. Under **Credentials > Create Credentials > OAuth client ID**, choose **Web Application**:
   - **Authorized redirect URIs**: `http://localhost:8000/api/social/youtube/callback`
5. Copy your Client ID and Client Secret into `.env`:
   ```ini
   YOUTUBE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
   YOUTUBE_CLIENT_SECRET=your_google_client_secret
   YOUTUBE_REDIRECT_URI=http://localhost:8000/api/social/youtube/callback
   ```

#### 2. Meta: Facebook Pages & Instagram Professional (Meta for Developers)
1. Go to [Meta for Developers](https://developers.facebook.com/) and create a Business App.
2. Add the **Facebook Login for Business** product.
3. Under **Facebook Login > Settings > Valid OAuth Redirect URIs**, enter:
   `http://localhost:8000/api/social/meta/callback`
4. Request permissions:
   - Facebook Pages: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
   - Instagram: `instagram_basic`, `instagram_content_publish`
5. Note: Instagram Reels publishing requires your Instagram Professional/Creator account to be linked to a Facebook Page, and requires an externally reachable HTTPS video URL (e.g. via ngrok tunnel in development).
6. Copy your App ID and App Secret into `.env`:
   ```ini
   META_APP_ID=your_meta_app_id
   META_APP_SECRET=your_meta_app_secret
   META_REDIRECT_URI=http://localhost:8000/api/social/meta/callback
   ```

#### 3. TikTok (TikTok for Developers)
1. Go to [TikTok for Developers](https://developers.tiktok.com/) and register a developer app.
2. Enable **Login Kit** and **Direct Post API** (Share Kit).
3. Set the Redirect URI to `http://localhost:8000/api/social/tiktok/callback`.
4. Copy your Client Key and Client Secret into `.env`:
   ```ini
   TIKTOK_CLIENT_KEY=your_tiktok_client_key
   TIKTOK_CLIENT_SECRET=your_tiktok_client_secret
   TIKTOK_REDIRECT_URI=http://localhost:8000/api/social/tiktok/callback
   ```
5. For personal use or while waiting for TikTok App Review, click **Prepare for TikTok** inside Reel Studio for 1-click MP4 download and caption copying!
