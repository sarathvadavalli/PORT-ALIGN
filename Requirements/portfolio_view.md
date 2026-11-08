
You are a senior Software developer working on an existing Portfolio Rebalancing System.

Your task is to implement two features:

1. **My Portfolio Page**
2. **Target Allocation Page**

Both features must strictly follow the requirements and constraints defined in `SPEC.md`.

## 1. Understand the existing project

Before implementation:

- Read the entire SPEC.md file before making any code changes.
- Inspect the existing Django models, views, URLs, templates, services, and database structure.
- Identify the existing InvestorProfile, Portfolio, Holding, Instrument, AssetClass, and TargetAllocation models, or their equivalents.
- Reuse the existing models and relationships wherever possible.
- Treat `SPEC.md` as the authoritative source of truth.
- Do not introduce additional business rules or assumptions.
- If any requirement is ambiguous or conflicts with the existing implementation, ask for clarification before proceeding.

## 2. My Portfolio Page

Create a page accessible from the authenticated investor's dashboard.

### Functional requirements

- Each investor is restricted to one portfolio for the initial version.
- Retrieve the portfolio associated with the currently authenticated investor.
- Display the  all instruments held in that portfolio.
- For each holding, display the instrument name, symbol (if available), asset class, quantity, average purchase cost, latest valid market price, and current market value.
- Calculate the market value of each holding as `quantity × latest valid price`.
- Display the total portfolio market value.
- Display the latest price date where applicable.
- Handle empty portfolios and missing market prices gracefully.
- Prevent investors from accessing another investor's portfolio by manipulating URLs or request parameters.

### Constraints

- Do not introduce support for multiple portfolios per investor.
- Do not create duplicate portfolios during page retrieval.
- Use the existing database relationships.
- Follow the market-price selection and missing-price rules documented in `SPEC.md`.
- Do not assume that the latest calendar date necessarily contains a valid market price.
- Do not implement portfolio evaluation, allocation drift, or rebalancing logic in this feature.
- Do not implement holding creation, modification, or deletion unless explicitly required by `SPEC.md`.

## 3. Target Allocation Page

Create a separate page accessible from the dashboard and optionally from the My Portfolio page.

### Functional requirements

- Allow the authenticated investor to view the target allocation associated with their portfolio.
- Allow the investor to define target allocation percentages for supported asset classes.
- Allow the investor to update the target allocation later.
- Validate that the sum of all target allocation percentages equals exactly 100%, using appropriate decimal precision.
- Reject negative percentages and percentages greater than 100%.
- Prevent duplicate target allocation entries for the same portfolio and asset class.
- Save target allocation changes atomically so that invalid or partial updates cannot leave the portfolio in an inconsistent state.
- Display clear validation messages for invalid input.
- If no target allocation exists, display an appropriate initial setup interface.

### Target allocation updates and proposal constraints

The system must preserve historical rebalancing proposals.

When a target allocation is successfully changed:

- Existing historical proposals must not be deleted.
- Pending proposals associated with the portfolio must be marked as `Outdated`, according to the status rules defined in `SPEC.md`.
- Completed, accepted, rejected, or other non-pending proposals must retain their existing statuses.
- If the submitted target allocation is identical to the currently saved allocation, do not unnecessarily invalidate pending proposals.
- Perform the target allocation update and relevant proposal status changes within the same database transaction.
- If the proposal model or status handling is not yet implemented, do not invent a new proposal workflow. Report the dependency and request clarification if necessary.

## 4. Authentication and authorization

- Both pages must require authentication.
- Resolve the investor's portfolio through the authenticated user and their associated investor profile.
- Never trust a client-supplied investor ID or portfolio ID for authorization.
- Prevent unauthorized access to portfolio holdings and target allocations.
- Follow the existing authentication mechanism and permissions defined in `SPEC.md`.

## 5. UI and navigation

Add the following navigation options to the existing dashboard:

- **My Portfolio** — View portfolio details and holdings.
- **Target Allocation** — View and manage desired asset-class allocations.

Provide navigation between the dashboard, portfolio page, and target allocation page.

Follow the existing UI framework, template structure, and styling conventions. Keep the interface responsive, clear, and consistent with the existing dashboard.

Do not introduce a new frontend framework.

## 6. Implementation guidelines

- Follow Django best practices.
- Keep database queries efficient and avoid N+1 query problems.
- Use Django ORM relationships and appropriate `select_related` or `prefetch_related` operations.
- Use `Decimal` for financial calculations and percentage validation; avoid floating-point arithmetic.
- Keep business logic separate from views where appropriate.
- Use database constraints in addition to application-level validation where required.
- Generate migrations only if necessary.
- Preserve existing database data and migrations.
- Do not modify unrelated modules.

## 7. Testing

Implement and execute tests covering:

**My Portfolio**

- Authenticated portfolio access.
- Unauthorized and cross-investor access restrictions.
- Correct holding retrieval.
- Correct market-value calculations.
- Empty portfolio handling.
- Missing market-price handling.

**Target Allocation**

- Initial target allocation creation.
- Successful target allocation updates.
- Allocation total not equal to 100%.
- Negative or invalid percentages.
- Duplicate asset-class allocations.
- Unauthorized updates.
- Atomic rollback on failure.
- Pending proposal invalidation after an actual target change.
- Preservation of historical proposals.
- No proposal invalidation when the target allocation is unchanged.

Only test proposal-related behavior when the relevant models and requirements exist.

## 8. Scope restrictions

Do not implement:

- Portfolio evaluation or allocation drift calculations.
- Rebalancing proposal generation.
- Trade recommendations or execution.
- Multiple portfolios per investor.
- Unspecified portfolio or holdings CRUD operations.
- Unrelated dashboard features.

## 9. Final verification

After implementation:

1. Summarize the functionality implemented.
2. List the files created or modified.
3. Explain any database migrations.
4. Report tests executed and their results.
5. Verify compliance with the relevant `SPEC.md` requirements.
6. Identify any unresolved dependencies or deviations.

**Important:** Do not modify `SPEC.md` without permission. If the existing codebase or specification conflicts with any requirement above, stop and request clarification rather than silently choosing an implementation.

The goal is to build two complete, secure, maintainable Django pages that integrate with the existing dashboard and provide the foundation for the future Portfolio Evaluation feature.
