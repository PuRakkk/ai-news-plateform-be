# AI News Automation Platform Backend (`ai-news-be`)

An automated intelligence and video production engine that scans breaking AI news, verifies facts across dual sources, scores stories for executive utility, writes strictly grounded short-form video scripts, and renders 9:16 vertical videos with neural voice and kinetic subtitles.

---

## 🌟 What the Platform Does

1. **Daily Ingestion & Dual-Source Verification (Stage 1-3)**:
   - Ingests breaking stories from authority news feeds (TechCrunch, VentureBeat, Reuters, MIT Tech Review, etc.).
   - Clusters related stories and cross-verifies facts against independent secondary sources.
2. **Dynamic Multi-Client Scoring (Stage 4)**:
   - Evaluates articles against each client's specific industry, focus keywords, and custom weights.
   - Automatically elects a personalized winning article for each client.
3. **Grounded Scriptwriting & Adversarial Claim Audit**:
   - Converts the winning story into an authoritative 5-beat executive short-form video script (*Hook, Context, Core Shift, Business Impact, CTA*).
   - Automatically audits every factual statement against the source article with verbatim quotes and auto-revises any ungrounded assertions.
4. **Non-Blocking Multimedia Video Synthesis**:
   - Programmatically synthesizes neural voiceover (EdgeTTS / ElevenLabs).
   - Generates kinetic word-highlighted subtitles (`.ass`), camera motion effects, brand watermarks, and presenter avatar cards in 1080x1920 (9:16 vertical) format.
   - Renders videos asynchronously in background worker threads without freezing FastAPI or the Admin Dashboard.

---

## 🛠️ Tech Stack & Requirements

| Component | Technology |
| :--- | :--- |
| **Language** | Python `3.11+` |
| **Package Manager** | [Astral `uv`](https://github.com/astral-sh/uv) (blazing fast virtualenv & dependency manager) |
| **Web Framework** | FastAPI + Uvicorn |
| **Database & ORM** | PostgreSQL 16 + SQLModel (SQLAlchemy 2.x + Pydantic v2) |
| **Database Migrations** | Alembic |
| **Cache & Job Queue** | Redis 7 + ARQ |
| **Admin Dashboard** | Starlette-Admin |
| **AI Models** | OpenAI (`gpt-4o-mini`) / Google Gemini (`gemini-2.5-flash`) |
| **Video Engine** | FFmpeg + Pillow + EdgeTTS |

---

## 📋 Prerequisites

Before starting, make sure you have installed on your machine:

1. **Python `>= 3.11`**
2. **Astral `uv`**:
   - **Windows (PowerShell)**: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - **macOS / Linux**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Or via pip: `pip install uv`
3. **Docker & Docker Compose** (for PostgreSQL and Redis)
4. **FFmpeg** (required for video rendering):
   - **Windows**: `choco install ffmpeg` or `winget install Gyan.FFmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt update && sudo apt install -y ffmpeg`
   - *Verify by running: `ffmpeg -version`*

---

## 🚀 Quick Start Guide (Get Running in 5 Minutes)

### Step 1: Install Dependencies
Clone the repository and sync all dependencies into a local virtual environment:
```bash
uv sync
```

### Step 2: Configure Environment Variables
Copy the template `.env.example` to `.env`:
```bash
# Windows PowerShell
cp .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and configure your API keys:
```env
# AI Model Selection (openai or gemini)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Or for Gemini:
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=...
```

### Step 3: Start Database & Redis (Docker)
Start the PostgreSQL 16 and Redis 7 containers:
```bash
make infra-up
# or manually: docker compose up -d db redis
```

### Step 4: Apply Database Migrations
Run Alembic migrations to set up the database schema:
```bash
make migrate
# or manually: uv run alembic upgrade head
```

### Step 5: Start the Development Server
```bash
make run
# or manually: uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 6: Start the Background Worker (Optional for Scheduled Jobs)
In a second terminal window, run the ARQ background worker:
```bash
make worker
# or manually: uv run arq app.core.worker.WorkerSettings
```

---

## 🌐 Key URLs & Admin Access

Once running, access the following in your browser:

- 📖 **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- ⚙️ **Admin Dashboard**: [http://localhost:8000/admin](http://localhost:8000/admin)
  - **Default Password**: `dev_admin_secret_key_1234567890` (configured via `ADMIN_AUTH_SECRET` in `.env`)
- 🏆 **Daily Elected Winner Page**: [http://localhost:8000/admin/winner](http://localhost:8000/admin/winner)
- 🩺 **Health Check**: [http://localhost:8000/healthz](http://localhost:8000/healthz)

---

## 💡 Common Development Workflows

### 1. Run News Ingestion & Scoring Manually
To scan RSS feeds, verify stories, and score candidates immediately:
```bash
make ingest
# or manually: uv run python -m app.services.ingestion.runner
```
Or trigger it via HTTP API:
```bash
curl -X POST http://localhost:8000/api/v1/news/ingest
```

### 2. Run the Automated Test Suite
Run all unit and integration tests across health, ingestion, media rendering, and scripting:
```bash
make test
# or manually: uv run pytest
```

### 3. Database Migrations
When modifying SQLModel models under `app/models/`:
```bash
# Generate a migration file
make revision name="describe_your_changes"

# Apply pending migrations
make migrate
```

### 4. Stop Docker Containers
```bash
make infra-down
```

---

## 📁 Project Architecture & Directory Layout

```text
ai-news/
├── app/
│   ├── core/               # App configuration, database engine, logging, auth, worker
│   ├── migrations/         # Alembic database migration revisions
│   ├── models/             # SQLModel database tables (Client, News, Script, Media)
│   ├── repositories/       # Data access layer & database queries
│   ├── routes/             # FastAPI API endpoints (HTTP validation & DTO mapping only)
│   ├── schemas/            # Pydantic request/response schemas (DTOs)
│   ├── services/           # Core business logic:
│   │   ├── admin/          # Starlette-Admin view definitions & actions
│   │   ├── ingestion/      # RSS polling, clustering, dual-source verifier, scorer
│   │   ├── llm/            # LLM adapter implementations (OpenAI, Gemini) & prompts
│   │   ├── media/          # Video rendering, canvas cards, subtitles, compositor, TTS
│   │   └── scripting/      # 5-beat scriptwriting & claim fact-checking auditor
│   └── main.py             # FastAPI application entrypoint & middleware setup
├── assets/                 # Default branding assets (avatars, audio bed, logos)
├── templates/              # Admin HTML templates (Daily Winner view, video players)
├── tests/                  # Pytest test suite (health, ingestion, media, scripting)
├── docker-compose.yml      # Local PostgreSQL & Redis infrastructure
├── Makefile                # Shortcut commands for development
├── pyproject.toml          # Project dependencies & tool configurations
└── uv.lock                 # Deterministic dependency lockfile
```

---

## 🔒 Architecture Rules (Strict Guidelines)

When contributing code, adhere to these project rules defined in `AGENTS.md`:

1. **Layer Separation**:
   - Routers (`app/routes/`) only handle HTTP validation and DTO response mapping. Never run business rules or database queries directly in routers.
   - Services (`app/services/`) hold core workflows and business logic.
   - Repositories (`app/repositories/`) hold database queries.
2. **Database & Migrations**:
   - Alembic owns all schema changes. Never run `SQLModel.metadata.create_all()` in runtime application code.
   - Always access the database via `get_session()` context manager or FastAPI `Depends(get_db)`.
3. **Non-blocking Media Processing**:
   - Heavy CPU tasks (FFmpeg video encoding, Pillow image creation) must run in worker threads (`asyncio.to_thread`) to prevent freezing the server.
4. **Idempotency & Secret Encryption**:
   - News pulls and automated scripts must be idempotent.
   - Provider API keys and webhook secrets must be encrypted using `SecretCipher`.

---

## ❓ Troubleshooting & FAQs

* **Error: `FFmpeg binary 'ffmpeg' not found in system PATH`**  
  *Make sure FFmpeg is installed and added to your system environment variables. Test in your terminal with `ffmpeg -version`.*
* **Error: `Connection refused` when connecting to Database or Redis**  
  *Make sure your Docker containers are running by executing `make infra-up`.*
* **Admin dashboard freezes or won't load**  
  *Ensure you're logged in with the secret key set in `ADMIN_AUTH_SECRET` in your `.env` file.*
