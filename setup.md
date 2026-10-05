# Topup Project Setup Master Prompt & Architecture Specification

This document contains the complete setup prompt, architecture specification, and reference blueprints for bootstrapping a new **ai-news-be** backend project based on the battle-tested patterns, security stack, database session lifecycle, and Alembic workflow of the `telegram-rag-chat-bot` codebase.

---

## How To Use

1. Create your new empty directory for the topup backend project:
   ```bash
   mkdir ai-news-be
   cd ai-news-be
   ```
2. Copy the **Master Prompt** below (everything between the start and end markers) and paste it into your AI assistant in your new project workspace.

---

```markdown
<!-- ================= START OF MASTER SETUP PROMPT ================= -->

# TASK: Initialize Secure ai-news-be Backend (FastAPI + SQLModel + Alembic + uv)

You are tasked with bootstrapping a brand-new, production-ready, highly secure backend project for a **Topup Website** (digital currency, game credits, mobile reloads, gift cards, or wallet topup platform).

Follow the exact architecture patterns, security practices, database session lifecycle, and Alembic migration setup described below.

> **CRITICAL INSTRUCTION FOR THIS INITIAL PHASE:**
> Do NOT create specific topup business models yet (no game packages, orders, or payment transactions schemas yet). 
> Keep `app/models/` empty (providing only a clean `app/models/__init__.py` exporting an empty list), so that the project skeleton, database connection pool, healthcheck, test runner, and Alembic migrations can run cleanly and pass tests out of the box.

---

## 1. Tech Stack & Dependencies

- **Python**: `>= 3.11`
- **Package Manager**: Astral `uv` (`pyproject.toml` with `uv.lock`)
- **Web Framework**: FastAPI with Uvicorn (`uvicorn[standard]`)
- **Database & ORM**: PostgreSQL (`psycopg2-binary`) with `sqlmodel` (SQLAlchemy 2.x + Pydantic v2 core)
- **Migrations**: Alembic (configured to store migrations under `app/migrations/`)
- **Settings & Validation**: `pydantic-settings>=2.12.0`, `email-validator>=2.3.0`
- **Authentication & Security**:
  - `pyjwt>=2.12.1` (HS256 access tokens)
  - `passlib[bcrypt]>=1.7.4` and `bcrypt<4.1` (password hashing)
  - `cryptography>=46.0.3` (Fernet symmetric encryption for sensitive provider credentials & API keys at rest)
  - `secrets` + `hmac` + `hashlib` (HMAC-SHA256 signature generation/verification with replay window checks for topup payment webhooks)
- **Admin Dashboard**: `starlette-admin==0.16.0` (mounted at `/admin` with session/secret auth)
- **Caching & HTTP Client**: `fastapi-cache2>=0.2.2`, `cachetools>=7.1.7`, `httpx>=0.28.1`
- **Testing**: `pytest>=9.0.0`, `pytest-asyncio>=1.4.0`

---

## 2. Directory Layout

Generate the following directory and file layout:

```text
.
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── Makefile
├── README.md
├── alembic.ini
├── docker-compose.yml
├── docker-entrypoint.sh
├── pyproject.toml
├── AGENTS.md
├── CLAUDE.md
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # Pydantic BaseSettings loading .env
│   │   ├── database.py           # Engine pool, SessionLocal, get_session contextmanager
│   │   ├── deps.py               # FastAPI dependency injection for DB session
│   │   ├── jwt.py                # Token creation and decoding with proper HTTP 401 exceptions
│   │   ├── security.py           # Bcrypt password hashing & secure OTP generator
│   │   ├── cipher.py             # Fernet secret encryption & HMAC-SHA256 webhook signatures
│   │   └── log.py                # Rotating file handler (5MB, 5 backups) + stdout logging
│   ├── models/
│   │   └── __init__.py           # Empty registry exporting `__all__ = []`
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── auth.py               # Base Auth request/response DTOs
│   ├── repositories/
│   │   └── __init__.py           # Base repository interface / empty registry
│   ├── services/
│   │   ├── __init__.py
│   │   └── admin/
│   │       ├── __init__.py
│   │       └── admin_setup.py    # StarletteAdmin configuration & auth provider
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── api_router.py         # Root API v1 router aggregator
│   │   ├── auth_deps.py          # Cookie/Bearer token extractor & auth dependencies
│   │   └── auth_routes.py        # Health, login/logout, profile endpoints
│   └── migrations/
│       ├── env.py                # Alembic runner reading from SQLModel.metadata & app.models
│       ├── script.py.mako
│       └── versions/
│           └── .gitkeep
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_health.py
```

---

## 3. Detailed File Specifications & Blueprints

### A. `pyproject.toml`
Configure Astral `uv` toolchain:
```toml
[project]
name = "topup-backend"
version = "0.1.0"
description = "Secure Topup Platform Backend with FastAPI, SQLModel, and Alembic"
requires-python = ">=3.11"

dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "sqlmodel",
    "alembic",
    "psycopg2-binary",
    "pydantic-settings>=2.12.0",
    "starlette-admin==0.16.0",
    "passlib[bcrypt]>=1.7.4",
    "bcrypt<4.1",
    "pyjwt>=2.12.1",
    "cryptography>=46.0.3",
    "httpx>=0.28.1",
    "email-validator>=2.3.0",
    "fastapi-cache2>=0.2.2",
    "cachetools>=7.1.7",
    "pytest>=9.0.0",
]

[dependency-groups]
dev = [
    "pytest-asyncio>=1.4.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

### B. Environment Configuration (`app/core/config.py` & `.env.example`)
Create `app/core/config.py` using `pydantic_settings.BaseSettings`:
- `APP_ENV`: `Literal["development", "test", "production"] = "production"`
- `DB_USER: str = "postgres"`
- `DB_PASSWORD: str = "postgres"`
- `DB_HOST: str = "localhost"`
- `DB_PORT: int = 5432`
- `DB_NAME: str = "topup_db"`
- `ADMIN_AUTH_SECRET: str = "change_this_to_a_long_admin_secret"`
- `JWT_SECRET: str = "change_this_to_a_long_random_secret"`
- `JWT_EXPIRE_MINUTES: int = 1440`
- `AUTH_COOKIE_NAME: str = "topup_auth"`
- `AUTH_COOKIE_SECURE: bool = False`
- `FRONTEND_CORS_ORIGINS: str = "http://localhost:3000"`
- `SECRET_ENCRYPTION_KEY: str | None = None` (Fernet 32-byte urlsafe base64 key)
- Helper properties:
  - `is_development -> bool`: `self.APP_ENV == "development"`
  - `cors_origins_list -> list[str]`: parse comma-separated `FRONTEND_CORS_ORIGINS`
- Model validator:
  - In production (`APP_ENV == "production"`), raise `ValueError` if `JWT_SECRET == "change_this_to_a_long_random_secret"` or if `SECRET_ENCRYPTION_KEY` is empty.

### C. Database Connection Pool & Session Management (`app/core/database.py`)
- Define `DATABASE_URL = f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"`
- Engine configuration:
  ```python
  engine = create_engine(
      DATABASE_URL,
      echo=False,
      pool_pre_ping=True,
      pool_size=50,
      max_overflow=20,
  )
  SessionLocal = sessionmaker(
      bind=engine,
      class_=Session,
      autoflush=False,
      autocommit=False,
      expire_on_commit=False,
  )
  ```
- Implement context manager `get_session()`:
  ```python
  @contextmanager
  def get_session():
      session: Session = SessionLocal()
      try:
          yield session
          if session.is_active:
              session.commit()
      except Exception:
          if session.is_active:
              session.rollback()
          raise
      finally:
          session.close()
  ```
- Implement `init_db()` placeholder function. Alembic owns the schema; do NOT call `SQLModel.metadata.create_all()`.

### D. Alembic Setup (`alembic.ini` & `app/migrations/env.py`)
- **`alembic.ini`**:
  - `script_location = app/migrations`
  - `file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d%%(second).2d_%%(rev)s_%%(slug)s`
  - `prepend_sys_path = .`
- **`app/migrations/env.py`**:
  - Load `.env` with `dotenv.load_dotenv()`
  - Import `SQLModel`
  - Import `from app.core.database import engine`
  - Import `import app.models` (registers all models with metadata)
  - `target_metadata = SQLModel.metadata`
  - Support offline and online migrations:
    ```python
    def run_migrations_online() -> None:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    ```

### E. Enterprise Security Suite
1. **At-Rest Secret Cipher (`app/core/cipher.py`)**:
   - `SecretCipher` class wrapping `cryptography.fernet.Fernet`.
   - Methods: `encrypt(plain: str) -> str` and `decrypt(cipher_text: str) -> str`.
   - Used for encrypting payment provider API secrets, merchant keys, and private webhook secrets.
2. **Webhook HMAC Signature Verification (`app/core/cipher.py`)**:
   - `sign_webhook(secret: str, timestamp: int, body: bytes) -> str`: produces `sha256=<hex_digest>` over `<timestamp>.<raw_body>`.
   - `verify_webhook_signature(secret: str, signature: str, timestamp: int, body: bytes, tolerance_seconds: int = 300) -> bool`:
     - Checks timestamp drift `abs(current_time - timestamp) <= tolerance_seconds` to prevent replay attacks.
     - Uses `hmac.compare_digest` to prevent timing attacks.
3. **SSRF Guard (`app/core/cipher.py`)**:
   - `validate_outbound_url(url: str) -> bool`:
     - Resolves hostname via DNS.
     - Blocks loopback (`127.0.0.1`, `::1`, `localhost`) and private IP blocks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`).
     - Ensures payment callback webhooks cannot be exploited for SSRF.
4. **JWT & Session Auth (`app/core/jwt.py` & `app/routes/auth_deps.py`)**:
   - `create_access_token(subject: str) -> str` with expiry timestamp.
   - `decode_access_token(token: str) -> str` returning subject, raising `HTTPException(401)` on expired or invalid token.
   - Dependency `get_current_account` reads from cookie `settings.AUTH_COOKIE_NAME` first, then falls back to `Authorization: Bearer <token>`.

### F. Application Lifespan & Server (`app/main.py`)
- FastAPICache initialization with `InMemoryBackend(prefix="topup-cache:")`.
- Setup logging via `app/core/log.py` (writes to `logs/app.log`, rotating at 5MB, keeping 5 backups).
- Startup validation: validates that `SECRET_ENCRYPTION_KEY` is a valid Fernet key if provided, and verifies production secrets.
- Middlewares:
  - `CORSMiddleware` with `allow_origins=settings.cors_origins_list`, `allow_credentials=True`.
  - HTTP Request performance & logging middleware measuring latency in ms, logging path, status code, duration, and client IP.
- Endpoints:
  - `GET /healthz`: returns `{"status": "ok"}`
  - Mount `app.include_router(api_v1_router, prefix="/api/v1")`
  - Mount `setup_admin(app)` at `/admin`

### G. DevOps & Containerization
- **`Dockerfile`**:
  - Base: `python:3.11-slim`
  - `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`
  - Installs system libraries (`libpq-dev`, `build-essential`, `curl`).
  - Installs dependencies using `uv pip install --system .`.
  - Runs as non-root user `appuser`.
  - Healthcheck on `http://127.0.0.1:8000/healthz`.
- **`docker-entrypoint.sh`**:
  ```sh
  #!/bin/sh
  set -eu
  alembic upgrade head
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*
  ```
- **`docker-compose.yml`**:
  - PostgreSQL 16 container (`topup-db`) with persistent volume and `pg_isready` healthcheck.
  - App container (`topup-app`) waiting for DB healthy status.
- **`Makefile`**:
  - `run`: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
  - `test`: `uv run pytest`
  - `migrate`: `uv run alembic upgrade head`

### H. Engineering Rules (`CLAUDE.md` / `AGENTS.md`)
Create `CLAUDE.md` and symlink/copy `AGENTS.md` specifying:
1. **Layered Boundaries**: `routes/` (HTTP parsing, validation, DTO mapping only) → `services/` (transactions, business logic, topup workflows) → `repositories/` (database queries) → `models/` (SQLModel). Never execute business or DB query logic directly in routers.
2. **Alembic Ownership**: Alembic owns all schema changes. Never call `create_all()`.
3. **Session Safety**: ORM model objects live inside active DB sessions; convert to Pydantic schemas before crossing async boundaries.
4. **Idempotency & Financial Safety**: Every topup transaction and webhook event MUST use idempotent processing with unique event keys. Balance updates must use append-only ledgers.
5. **Truthiness Style**: Use `if not variable:` instead of `if variable is None:`.

---

## 4. Immediate Execution

Generate all files, configurations, directories, tests, and scripts now.
Verify that:
1. `uv sync` installs all dependencies without conflicts.
2. `pytest` executes and passes tests.
3. `uv run uvicorn app.main:app --reload` starts the server and `GET /healthz` returns `{"status": "ok"}`.

<!-- ================== END OF MASTER SETUP PROMPT ================== -->
```

---

## Architecture Blueprint Reference (Why these libraries and patterns?)

| Component / Library | Selection Reason for Topup Platform |
| :--- | :--- |
| **`uv` Toolchain** | Ultra-fast dependency resolution and virtualenv creation. Clean `pyproject.toml` configuration. |
| **`SQLModel` + PostgreSQL** | Combines SQLAlchemy 2.0 with Pydantic v2. Provides strict type safety and direct serialization for API endpoints. |
| **Alembic (`app/migrations`)** | Zero-downtime database migrations with automated timestamped version naming (`file_template`). |
| **Connection Pooling** | `pool_pre_ping=True`, `pool_size=50`, `max_overflow=20` handles high-concurrency topup spikes and drops stale DB connections cleanly. |
| **`SecretCipher` (Fernet)** | Topup platforms integrate with third-party payment gateways and mobile reloads. Fernet allows encrypting provider API secrets and private merchant keys securely in the database at rest. |
| **HMAC-SHA256 Signatures** | Webhooks from payment gateways require cryptographic signature verification and timestamp tolerance checks to prevent replay attacks. |
| **SSRF URL Guard** | If your topup platform supports merchant callbacks or webhooks, outbound URLs must be screened against loopback and RFC1918 internal subnets to protect internal services. |
| **Context Manager `get_session()`** | Explicit transaction scope with automatic commit on success and rollback on any failure. Eliminates leaking connections. |
| **Starlette-Admin** | Lightweight operational backoffice interface mounted at `/admin` for viewing accounts, topup orders, and transaction ledgers without writing a separate admin frontend. |
