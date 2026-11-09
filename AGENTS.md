# PORT ALIGN

## Purpose

This repository implements an educational portfolio rebalancing simulator. It evaluates portfolio allocations and generates proposed trades; it **does not execute real trades** or provide personalized investment advice.

Before editing, inspect the repository, existing models, migrations, tests, and any `SPEC.md` or feature instructions. Existing code and explicit specifications take precedence over assumptions in this file. Keep changes focused and explain important trade-offs.

## Tech stack

- Python, Django (server-rendered templates and/or existing APIs)
- MySQL as the authoritative relational database
- Django ORM, Django authentication, HTML/CSS/JavaScript as already used in the repository
- Existing price-ingestion integration and scheduling mechanism, if present

Do not introduce React, Celery, Redis, new external services, or additional dependencies unless a feature explicitly requires them and the change is approved.

## Project structure

Discover the actual layout before making changes; do not assume these names already exist. Prefer the repository's current organization:

```text
project-root/
├── AGENTS.md                 # Codex guidance
├── SPEC.md                   # Product and feature requirements
├── manage.py                 # Django management entry point
├── requirements.txt          # Python dependencies (or pyproject.toml)
├── PortAlign/                # Django settings, URLs, WSGI
├── myapp/                    # Models, views, forms, services, URLs, tests
│   ├── migrations/
│   ├── templates/
|   ├── static/
|   ├── urls.py
|   ├── views.py
|   ├── models.py
|   ├── forms.py
│   └── tests                 # Unit and Integration tests
├── Features                  # Instructions for each feature
```

Keep HTTP views thin. Put nontrivial valuation, allocation, proposal, and validation logic in reusable service functions/modules. Avoid circular imports and unnecessary new apps.

## Common commands

Run commands from the directory containing `manage.py`. Confirm the environment and dependency files first; adjust commands to the repository's setup.

```bash
# Create and activate a virtual environment (Linux/macOS)
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

# Install dependencies (if requirements.txt exists)
python -m pip install -r requirements.txt

# Django checks and local server
python manage.py check
python manage.py runserver

# Inspect and apply migrations
python manage.py makemigrations --check --dry-run
python manage.py migrate

# Run tests
python manage.py test

# Check for pending migrations after model edits
python manage.py makemigrations --check --dry-run
```

Use a dedicated test database and environment variables for database credentials. Never run destructive migration, flush, reset, or data-loading commands against production. If the repository defines pytest, linting, formatting, or deployment commands, prefer those established commands and document any new ones.

## Coding standards

- Follow the existing repository style, Django conventions, and installed formatter/linter configuration.
- Use clear Python names, small functions, type hints for service-layer interfaces where practical, and concise docstrings for non-obvious business rules.
- Prefer Django ORM and parameterized queries. Avoid raw SQL unless justified by a measured query or feature requirement.
- Use `Decimal` for money, quantities where precision matters, percentages, and fees; avoid binary floats in financial calculations. Define rounding/precision explicitly and avoid premature rounding during intermediate calculations.
- Use `select_related`, `prefetch_related`, and appropriate indexes to prevent N+1 queries. Inspect query plans before adding speculative indexes.
- Use Django forms/serializers and model/database constraints for validation. Do not rely solely on browser-side validation.
- Use `transaction.atomic()` for multi-row changes that must succeed or fail together, especially target-version creation and proposal persistence. Handle concurrent version creation safely.
- Keep timestamps timezone-aware. Follow existing naming, URL, template, and error-response conventions.

## Security and boundaries

- Enforce authentication and per-object ownership on all investor-facing routes and queries.
- Use Django's CSRF protection and standard password/authentication facilities; do not implement custom cryptography or store plaintext credentials.
- Keep secrets and database configuration in environment variables, never committed source files. Do not modify `.env` secrets.
- Do not delete data, rewrite migration history, alter unrelated apps, or perform broad refactors as part of a narrow task.
- Do not change schema, public API contracts, or business policies silently. Create migrations for intentional schema changes and explain compatibility implications.

When specifications conflict, prioritize the user's current explicit instructions, then the project's authoritative specification and existing invariants. Surface conflicts rather than silently choosing a new financial rule.
