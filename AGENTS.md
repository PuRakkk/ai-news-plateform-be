# Engineering Guidelines & Architecture Rules

## 1. Architectural Boundaries
- **Strict Layered Separation**:
  - `app/routes/`: HTTP parsing, request validation, authentication, and DTO response mapping only. Never execute business rules or raw database queries directly in routers.
  - `app/services/`: Core business logic, pipeline orchestration, workflows, and transaction boundaries.
  - `app/repositories/`: Data access logic and SQLModel database queries.
  - `app/models/`: SQLModel table declarations and database schemas.
  - `app/schemas/`: Pydantic request/response schemas (DTOs).

## 2. Database & Migrations
- **Alembic Ownership**: Alembic owns all schema changes. Never execute `SQLModel.metadata.create_all()` in runtime code or migrations.
- **Session Safety**: ORM model instances live inside active database sessions. Always map models to Pydantic schema DTOs before crossing async boundaries or returning responses.
- **Connection Lifecycle**: Always access the database via the `get_session()` context manager or FastAPI `Depends(get_db)`.

## 3. Security & Idempotency
- **Idempotency**: All background automation tasks, scheduled news pulls, content generation, and webhook triggers must be idempotent using unique idempotency keys.
- **Secret Encryption**: Sensitive provider API keys, webhook secrets, and external credentials must be encrypted at rest using `SecretCipher` (Fernet).
- **Outbound Webhooks & SSRF**: External HTTP requests to user-provided URLs must pass `validate_outbound_url` to prevent SSRF vulnerabilities.

## 4. Code Style & Conventions
- **Truthiness**: Prefer `if not variable:` instead of `if variable is None:` when checking for empty/falsy values unless explicit distinction between `None` and falsy is mandatory.
- **Type Annotations**: All functions, methods, and endpoint signatures must have complete type hints.
