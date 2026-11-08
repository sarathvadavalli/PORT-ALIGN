# Authentication implementation

Scope: SPEC.md FR-20 through FR-25 and applicable account integrity/security requirements. SPEC.md is unchanged.

## Confirmed decisions

- Existing LOW/MODERATE/HIGH risk levels; MODERATE at registration; direct investor edits allowed.
- Independent 400 ms username/email debounce timers; existing Django password validators.
- Automatic one-to-one InvestorProfile creation under FR-25; no portfolio creation or linking.
- Email verification and account recovery excluded by agreement.

## Requirement checklist

| Specification | Implementation | Verification |
| --- | --- | --- |
| FR-20 | Required username, email, password, first/last names; optional validated phone; field-specific errors. | Registration, required/invalid input, duplicates, database uniqueness tests. |
| FR-21 | Independent timers, accessible per-field feedback, stale-response protection; final form checks plus database uniqueness. | Availability/final-recheck Django test, duplicate race test, Node debounce test. |
| FR-22 | Valid email identifiers resolve by email; other identifiers resolve by username. Django authenticates hashed passwords and manages sessions; invalid/inactive accounts receive generic errors. | Both identifiers, session identity, generic errors, inactive user tests. |
| FR-23 | Login always opens dashboard. Dashboard/profile require sessions; navigation exposes profile. No portfolio actions exist or were added. | Redirect, access, ownership, CSRF, logout tests. |
| FR-24 | View/edit own username, email, first/last names, optional phone and linked risk level. Transactions preserve data on rejected saves. | Display, valid/invalid update, unchanged uniqueness, ownership injection and rollback tests. |
| FR-25 | Registration transaction creates User and InvestorProfile. A singleton sequence row locked with SELECT FOR UPDATE allocates INV-000001-style IDs; seeded from existing IDs. Model saves reject changed IDs and caller-assigned IDs for new profiles. | Hashed password/profile creation, distinct concurrent IDs, duplicate registration races, sequence rollback, immutability and non-reuse tests. |
| NFR-04, NFR-16 | Existing database username uniqueness plus unique email constraint; one-to-one user link and primary-key uniqueness. Existing MySQL collation makes account uniqueness case insensitive. | Direct database duplicate writes, including case variants, are rejected. |
| NFR-05, NFR-06, NFR-15 | Django hashing, session login/logout, CSRF middleware/tokens and own-profile access; editable fields are explicitly allowlisted. | Password, session, CSRF, ownership and privilege-field injection tests. |
| NFR-12 | This document records decisions, routes, sequence behavior and migration handling. | Code/migration review and Django system checks. |

## Routes

`/register/`, `/login/`, `/logout/` (POST), `/availability/` (GET, field/value), `/dashboard/`, `/profile/`.

Registration redirects to login. Profile updates redirect back to profile. Accounts without a linked profile receive 404 rather than silently receiving a new identity.

## Changed files

- `myapp/models.py`: InvestorSequence; ID allocation/immutability; corrected profile string representation.
- `myapp/forms.py`: registration/account/profile forms and identifier authentication form.
- `myapp/views.py`, `myapp/urls.py`: routes, views, duplicate handling and access protection.
- `PortAlign/settings.py`: named login and dashboard redirects.
- `myapp/templates/myapp/`: base, registration, login, dashboard and profile templates.
- `myapp/static/myapp/availability.js`: debounced availability feedback.
- `myapp/tests.py`, `myapp/availability.test.cjs`: server and JavaScript tests.
- `myapp/migrations/0002_remove_portfolio_portfolio_cash_nonneg_and_more.py`: repair duplicate constraint operation that previously prevented creating a fresh database. Already-applied installations do not rerun it.
- `myapp/migrations/0007_reconcile_profile_schema.py`: reconcile migration state and live profile columns; copy legacy account data before dropping legacy columns on fresh installations, rejecting conflicts. Preserve existing phone/risk values. This migration is intentionally irreversible.
- `myapp/migrations/0008_registration_integrity.py`: create/seed investor sequence and enforce unique auth_user email without replacing Django User or deleting duplicates. Conflicting emails block migration for manual reconciliation.
- `Requirements/authentication-implementation.md`: implementation and verification record.

## Verification

Run from the project directory:

```text
python manage.py test myapp --noinput
node --test myapp/availability.test.cjs
python manage.py check
python manage.py makemigrations --check --dry-run
```

Tests use an isolated MySQL test database, including actual concurrent connections. The Node test uses controlled timers/network responses to verify debounce behavior without dependencies.

Results: all 22 Django tests passed, including concurrency tests; all eight targeted registration/profile tests passed again after the final empty-POST validation adjustment. The Node debounce test passed. Django system checks passed and the migration drift check reported no changes.

Migrations 0007 and 0008 were applied to the existing database. A before/after comparison of every field on all 1,000 users and 1,000 investor profiles confirmed their data remained identical. The sequence starts after INV-001000 on this installation. The existing historical migration 0006 is retained; its placeholder user default is not an account-linking policy for importing legacy unlinked datasets.

No portfolio functionality, new roles, recovery flows or verification flows were introduced. Concurrent allocation assumes the configured MySQL/InnoDB database. ID space is limited to six digits by the existing ten-character investor_id field; exhaustion rejects registration atomically. No claim is made that raw SQL or QuerySet.update enforces model-level ID immutability.
