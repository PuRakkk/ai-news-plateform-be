# AI News Automation Platform Backend (`ai-news-be`)

A production-ready, highly secure backend engine for scanning AI news, multi-source verification, business scoring, autonomous multimedia content creation, and multi-channel social publishing.

## Tech Stack
- **Python**: `>=3.11`
- **Package Manager**: Astral `uv`
- **Framework**: FastAPI + Uvicorn
- **ORM & Database**: SQLModel + PostgreSQL 16 (Docker)
- **Cache & Task Queue**: Redis 7 (Docker) + ARQ
- **Migrations**: Alembic
- **Admin**: Starlette-Admin
- **LLM Engine**: Pluggable Gemini / OpenAI with Google Search & Web Grounding
- **Security**: HS256 JWT, Fernet SecretCipher, HMAC-SHA256 signatures, SSRF protection

---

## Quick Start (Development Workflow)

### 1. Environment Setup
```bash
# Install uv toolchain & virtualenv
uv sync

# Configure environment variables
cp .env.example .env
```

### 2. Start PostgreSQL & Redis Infrastructure
```bash
make infra-up        # Runs PostgreSQL 16 & Redis 7 in Docker
```

### 3. Run Database Migrations
```bash
make migrate         # Applies Alembic migrations
```

### 4. Start Development Services
```bash
# Terminal 1: FastAPI Web Server (with auto-reload)
make run             # Starts on http://localhost:8000

# Terminal 2: Background Task Worker & 7:00 AM Cron
make worker          # Starts ARQ background worker
```

- **Health check**: `http://localhost:8000/healthz`
- **API Docs (Swagger)**: `http://localhost:8000/docs`
- **Admin Dashboard**: `http://localhost:8000/admin`

### 5. Running Tests
```bash
make test            # Runs pytest test suite
```

### 6. Stop Infrastructure
```bash
make infra-down      # Stops Docker containers
```
