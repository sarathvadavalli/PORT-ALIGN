You are a senior Software developer working on an existing project.

Your task is to implement the **Authentication and Investor Profile modules** strictly according to the requirements documented in `SPEC.md`.

### 1. Read and understand the specification

- Read the entire `SPEC.md` file before making any code changes.
- Identify all requirements related to authentication, registration, login, logout, user management, investor profiles, permissions, and validation.
- Examine the existing Django project structure, models, views, URLs, settings, and dependencies.
- Treat `SPEC.md` as the **single source of truth** for functional requirements.
- Do not introduce additional features, fields, endpoints, roles, or business rules that are not specified.
- If any requirement is ambiguous, contradictory, or missing critical information, ask for clarification before implementing it. Do not make assumptions.

### 2. Implementation requirements

- Follow the existing project architecture, coding conventions, and technology stack.
- Reuse Django's built-in authentication functionality wherever appropriate and consistent with the specification.
- Implement the User and Investor Profile models and their relationships exactly as specified.
- Implement registration, login, logout, profile creation, profile retrieval, and profile updates only to the extent required by `SPEC.md`.
- Enforce all specified authentication, authorization, uniqueness, and validation rules.
- Ensure sensitive information such as passwords is handled securely using Django's supported mechanisms.
- Do not allow users to access or modify another user's profile unless explicitly permitted by the specification.
- Use database transactions where required to maintain data consistency.
- Do not modify unrelated modules or existing functionality.

### 3. Database and migrations

- Review existing models before creating or modifying tables.
- Avoid duplicating existing fields or relationships.
- Generate Django migrations for any necessary schema changes.
- Preserve existing data and database compatibility.
- Do not delete or reset existing database records.

### 4. Testing

Write and execute tests covering all applicable requirements from `SPEC.md`, including:

- Successful registration and authentication.
- Invalid input and duplicate registration.
- Password handling.
- Profile creation and retrieval.
- Profile updates and validation.
- Authentication and authorization restrictions.
- Relevant edge cases and failure scenarios.

Tests must verify the specified behavior rather than assumptions about intended functionality.

### 5. Scope restrictions

- Implement **only Authentication and Investor Profile features**.
- Do not implement portfolio management, holdings, instruments, market prices, rebalancing, or other unrelated modules.
- Do not add optional enhancements or speculative functionality.
- Do not change `SPEC.md` without explicit permission.
- Avoid unnecessary refactoring, new dependencies, or architectural changes.

### 6. Execution workflow

1. Read `SPEC.md` and inspect the existing codebase.
2. Summarize the authentication and profile requirements you identified.
3. Identify any ambiguities or blockers and request clarification if necessary.
4. Prepare a concise implementation plan mapping requirements to affected files.
5. Implement the features.
6. Create and run the relevant tests.
7. Review the implementation against every applicable requirement in `SPEC.md`.

### 7. Final deliverables

After implementation, provide:

- A summary of implemented functionality.
- A list of files created or modified.
- Database migrations introduced.
- Tests executed and their results.
- A requirement-by-requirement compliance checklist referencing `SPEC.md`.
- Any incomplete requirements, blockers, or deviations.

**Important:** Do not claim that a requirement is implemented unless it is supported by the code and verified where possible. Do not silently deviate from `SPEC.md`.

The objective is a minimal, secure, maintainable implementation that satisfies the documented requirements without expanding the scope.
