# AI News Automation Platform Backend (`ai-news-be`)

A production-ready, highly secure backend engine for scanning AI news, multi-source verification, business scoring, autonomous multimedia content creation, and multi-channel social publishing.

## Tech Stack
- **Python**: `>=3.11`
- **Package Manager**: Astral `uv`
- **Framework**: FastAPI + Uvicorn
- **ORM & Database**: SQLModel (SQLAlchemy 2.x + Pydantic v2) + PostgreSQL
- **Migrations**: Alembic
- **Admin**: Starlette-Admin
- **Security**: HS256 JWT, Fernet SecretCipher, HMAC-SHA256 signatures, SSRF protection

## Quick Start

### 1. Environment Setup
```bash
# Install uv toolchain & virtualenv
uv sync

# Copy environment variables
cp .env.example .env
```

### 2. Run Database Migrations
```bash
uv run alembic upgrade head
```

### 3. Start Development Server
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Health check**: `http://localhost:8000/healthz`
- **API Docs (Swagger)**: `http://localhost:8000/docs`
- **Admin Dashboard**: `http://localhost:8000/admin`

### 4. Running Tests
```bash
uv run pytest
```
