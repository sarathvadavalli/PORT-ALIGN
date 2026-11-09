# SPEC.md — On-Demand Portfolio Rebalancing Recommendation System

**Status:** Draft v1.2 — decisions 1–6 confirmed; remaining policy decisions pending
**System type:** Educational portfolio evaluation and rebalancing simulation
**Operating model:** On-demand; no automatic trading or market-price-triggered proposals

## 1. Goal

Build a system that allows an investor or operations analyst to request an evaluation of an existing investment portfolio against its configured target asset allocation. The system calculates current allocation and drift using applicable market prices. When rebalancing is explicitly requested and permitted by policy, it generates a constraint-aware trade proposal, simulates the expected post-trade allocation, and saves the proposal and supporting decisions for review.

The system provides **recommendations and simulations only**. It does not execute trades or provide personalized financial advice.

### Success criteria

- Current portfolio values and asset-class weights reconcile with holdings and applicable prices.
- Allocation drift is calculated against a valid target allocation.
- Proposed trades satisfy applicable policy constraints, or the proposal clearly records exceptions and is not represented as valid.
- Estimated fees and simulated post-trade holdings/weights reconcile.
- Every evaluation and saved proposal can be traced to its input snapshot, policy assumptions, calculations, and outcome.

## 2. Target users

| User                                 | Primary needs                                                                                               |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| **Investor / account holder**  | Request an evaluation of their own portfolio; review current allocation, drift, and any available proposal. |
| **Operations analyst**         | Evaluate authorized portfolios, request proposals, inspect calculations, and review exceptions.             |
| **Risk / compliance reviewer** | Review proposal policy compliance, constraint violations, and decision history.                             |
| **System administrator**       | Maintain authorized reference/configuration data and oversee data quality and system operations.            |

**Access principle:** A user may only access portfolios and actions for which they are authorized. Detailed role permissions remain to be finalized.

## 3. Scope and workflow

### In scope

- User registration, login, session authentication, dashboard access, and investor profile viewing/editing.

1. Accept an on-demand portfolio evaluation request.
2. Retrieve the portfolio, holdings, target allocation, relevant instrument metadata, market prices, and applicable constraints/fees.
3. Validate input completeness, freshness, and arithmetic consistency.
4. Compute portfolio market value, current asset-class weights, and drift from targets.
5. Compare absolute drift against the ±5 percentage-point safe limit and ±2 percentage-point post-rebalancing tolerance.
6. Only on an explicit rebalancing request, attempt a proposal if any asset-class drift exceeds ±2 percentage points; notify the investor when all drifts remain within the ±5-point safe limit.
7. Validate instrument-level minimum trade sizes and funding using existing portfolio cash and sale proceeds only; estimate fees, simulate post-trade holdings and allocations, and request investor confirmation after displaying estimated costs.
8. Persist the evaluation, proposal (when generated), validation findings, and decision history for review.
9. Support synthetic datasets, labeled exception cases, and reproducible evaluation.

### Out of scope

- Automatic evaluation or proposal generation in response to market-price changes.
- Sending orders to brokers, executing trades, or transferring money.
- Guaranteeing investment performance or giving financial advice.
- Automatic approval or execution of proposals.

### Primary on-demand workflow

1. **Request:** An authorized investor or operations analyst selects a portfolio and requests an evaluation, optionally asking for a rebalancing proposal.
2. **Retrieve:** The system loads a consistent set of holdings, target weights, instrument details, applicable dated prices, fee schedules, and constraints.
3. **Evaluate:** It validates inputs, calculates portfolio value, current weights, and drift, and reports the result.
4. **Decide:** Show whether any asset-class drift exceeds ±5 percentage points. If rebalancing is explicitly requested, proceed only when at least one asset-class drift exceeds ±2 percentage points; otherwise return a no-rebalance message.
5. **Propose:** Prepare candidate buy/sell trades to bring every asset-class drift within ±2 percentage points. If all drifts are within ±5 points, explain that the portfolio is within the safe limit, but allow the explicitly requested proposal when any drift exceeds ±2 points.
6. **Validate and simulate:** Apply instrument-specific minimum trade sizes; fund purchases and fees using portfolio cash and sale proceeds only. Account for sale proceeds before funded purchases. If insufficient cash remains, roll back the simulated rebalancing and show "No enough cash available to buy". Calculate estimated fees and recompute post-trade allocation.
7. **Confirm, persist, and review:** Display the proposal and estimated costs and ask the investor to confirm. Preserve the evaluation, proposal (if feasible), simulation, confirmation state, exceptions, and audit information for review; confirmation is not trade execution.

**Important distinction:** Evaluation is always the primary requested operation. A proposal is conditional; it must not be generated solely because drift exists.

## 4. Functional requirements

| ID    | Requirement                                | Expected behavior                                                                                                                                                                                                                                                                                                                                                                             |
| ----- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-01 | On-demand initiation                       | Accept an authorized request identifying the portfolio and provide a rebalance proposal if requested.                                                                                                                                                                                                                                                                                         |
| FR-02 | Portfolio retrieval                        | Retrieve the portfolio's investor profile, instruments, holdings, and target allocation.                                                                                                                                                                                                                                                                                                      |
| FR-03 | Market-price selection                     | Select prices applicable to the evaluation's as-of date and identify missing or stale prices.                                                                                                                                                                                                                                                                                                 |
| FR-04 | Input validation                           | Check valid IDs/relationships, quantities, target weights, dates, and required data before using them.                                                                                                                                                                                                                                                                                        |
| FR-05 | Current valuation                          | Calculate instrument and portfolio values from holdings and prices; calculate current asset-class weights.                                                                                                                                                                                                                                                                                    |
| FR-06 | Drift analysis                             | Calculate differences between current and target weights and identify over-/under-allocated asset classes.                                                                                                                                                                                                                                                                                    |
| FR-07 | Policy eligibility                         | Flag drift outside ±5 percentage points as beyond the safe limit. An explicit rebalancing request is allowed if any asset-class drift is outside ±2 points, including when all drifts are within ±5 points. If all drifts are within ±2 points, do not propose trades.                                                                                                                    |
| FR-08 | Proposal generation                        | Only on explicit request and when eligible, generate candidate trades to bring each asset-class drift within ±2 percentage points without violating constraints.                                                                                                                                                                                                                             |
| FR-09 | Constraint validation                      | Apply instrument-specific minimum trade sizes, available holdings, applicable fee rules, and other constraints whose detailed policies remain pending. No external cash contributions are allowed.                                                                                                                                                                                            |
| FR-10 | Fee estimation                             | Calculate estimated fees for buys and sells, deduct them from portfolio cash (including proceeds of sales), and include them in the proposal costs shown to the investor. Exact fee schedule and rounding rules remain pending.                                                                                                                                                               |
| FR-11 | Post-trade simulation                      | Simulate sales, available cash, buys, fees, holdings, and post-trade allocation; if available cash cannot cover required purchases and fees, roll back the simulated rebalancing without partially applying trades and display "No enough cash available to buy".                                                                                                                             |
| FR-12 | Outcome classification                     | Distinguish evaluated-only, within-safe-limit with optional requested rebalance, no-rebalance-needed (all drifts within ±2 points), proposal awaiting confirmation, infeasible proposal, and data/policy exceptions.                                                                                                                                                                         |
| FR-13 | Reviewable records                         | Save evaluation inputs/references, calculated results, proposal details, simulation, validation findings, timestamps, and status.                                                                                                                                                                                                                                                             |
| FR-14 | Historical traceability                    | Preserve prior evaluations, proposals, and status changes rather than overwriting their history.                                                                                                                                                                                                                                                                                              |
| FR-15 | Authorized review                          | Allow permitted users to retrieve past evaluations, proposals, and explanations.                                                                                                                                                                                                                                                                                                              |
| FR-16 | Synthetic data support                     | Support the problem statement's synthetic investors, portfolios, instruments, holdings, prices, policies, and labeled anomalies.                                                                                                                                                                                                                                                              |
| FR-17 | Reproducible validation                    | Validate generated data and compare repeated fixed-seed generation runs for consistent outputs.                                                                                                                                                                                                                                                                                               |
| FR-18 | Investor confirmation                      | Before an eligible proposal proceeds to review, show estimated rebalancing costs and ask the investor to confirm; do not treat confirmation as actual trade execution.                                                                                                                                                                                                                        |
| FR-19 | Safe-limit messaging                       | When every asset-class drift is within ±5 points, show that the portfolio is within the safe limit. If any drift exceeds ±2 points, an explicitly requested proposal may still be generated.                                                                                                                                                                                                |
| FR-20 | User registration                          | Provide a registration form requiring username, email, password, first name, and last name; phone number is optional. Validate required fields and prevent duplicate usernames and email addresses before creating an account.                                                                                                                                                                |
| FR-21 | Debounced availability checks              | Check username and email availability independently after the user pauses typing in each respective field (debouncing). Show field-specific availability/duplicate feedback. Repeat uniqueness checks on final submission to prevent race conditions; debouncing is not a substitute for server-side validation.                                                                              |
| FR-22 | User login and session authentication      | Accept a username **or** email address plus password. Determine the identifier type, retrieve the matching user, verify the password using Django authentication/password hashing, establish a Django-managed authenticated session on success, and reject invalid credentials without disclosing whether an account exists.                                                            |
| FR-23 | Authenticated dashboard and profile access | Redirect the user to the dashboard after successful login. Provide a profile-view option accessible to the authenticated user. Protect dashboard, profile, and portfolio actions using Django session authentication and applicable authorization checks.                                                                                                                                     |
| FR-24 | View and edit profile                      | Display the authenticated user's username, email, first name, last name, optional phone number, and risk profile sourced from the linked `InvestorProfile`. Allow the user to edit and save these details, validate submitted values, and enforce username/email uniqueness on updates. The allowed risk-profile values and whether changes require additional review remain to be defined. |
| FR-25 | Automatic InvestorProfile Creation         | Upon successful registration, the system shall automatically create an InvestorProfile linked one-to-one with the newly registered Django User. The system shall generate a unique, immutable investor ID following the INV-000001 convention, using concurrency-safe sequence allocation. User creation and investor-profile creation shall be atomic.                                       |

### Confirmed policy and decision rules (decisions 1–6)

- **Drift units:** Thresholds refer to **percentage-point differences** between current and target asset-class weights. For each class, `drift = current_weight − target_weight`.
- **Safe limit:** An asset class is within the safe limit when its drift is between **−5 and +5 percentage points**, inclusive. Display a safe-limit message when all asset classes meet this condition.
- **Post-rebalancing goal:** A feasible proposal must bring **every asset class** to between **−2 and +2 percentage points**, inclusive, of its target.
- **On-demand only:** Do not generate a proposal automatically. A user must explicitly request rebalancing.
- **Optional rebalancing inside safe limit:** When all asset classes are within ±5 points but one or more are outside ±2 points, the user may explicitly request rebalancing. Show the safe-limit message, proposed costs, and a confirmation request.
- **Already within ±2:** When all asset classes are within ±2 points, **do not rebalance**, even on explicit request; display a no-rebalancing-needed message.
- **Funding:** No additional cash may be deposited or assumed. Purchases and fees must be covered by existing portfolio cash and proceeds from proposed sales. Fees reduce available portfolio cash; selling proceeds may be used to cover fees and subsequent purchases.
- **Insufficient funding:** If the proposed purchases and fees cannot be funded, **roll back the simulated rebalancing as a whole** and display the exact message: **"No enough cash available to buy"**. Do not save an infeasible candidate as a valid proposal; preserve diagnostic/audit information.
- **Minimum trade sizes:** Set and validate minimum trade sizes **per individual instrument**.
- **Confirmation:** Show estimated costs and ask the investor to confirm the proposal. Confirmation does not execute trades.

### Other rules retained from the problem statement; details not yet confirmed

- Target allocation weights must sum to 100% for a valid baseline; current weights are calculated from holdings and prices.
- A sell must not exceed available holdings; applicable exclusions and liquidity restrictions must be checked, but their precise behavior remains unresolved.
- Missing or stale prices, omitted fees, and inconsistent weights must be flagged rather than silently accepted.
- If no feasible proposal achieves the ±2-point goal under applicable constraints, return a documented infeasible/no-proposal outcome.
- A simulated allocation is hypothetical, not proof of trade execution.

## 5. Non-functional requirements

| ID     | Category               | Requirement                                                                                                                                                                   |
| ------ | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-01 | Correctness            | Derived values must reconcile to source holdings, prices, trades, and fees within documented numerical tolerances.                                                            |
| NFR-02 | Determinism            | Identical inputs, as-of date, policy version, and calculation version must produce the same result.                                                                           |
| NFR-03 | Traceability           | Every decision must be attributable to an evaluation request, input data versions/snapshot, applied rules, and timestamps.                                                    |
| NFR-04 | Data integrity         | Enforce primary-key uniqueness, foreign-key validity, allowed values, date ordering, and valid lifecycle transitions.                                                         |
| NFR-05 | Security               | Enforce authentication and authorization for portfolio access, configuration changes, and review actions.                                                                     |
| NFR-06 | Privacy                | Avoid real personal or confidential data in synthetic datasets; protect any user-associated portfolio data.                                                                   |
| NFR-07 | Reliability            | Handle incomplete prices, inconsistent holdings, invalid targets, and constraint conflicts with explicit error/exception outcomes.                                            |
| NFR-08 | Performance            | Support interactive on-demand evaluation; response-time targets and concurrency limits require measurement and agreement.                                                     |
| NFR-09 | Scalability            | Support the baseline educational dataset: approximately 1,000 portfolios, 2,000 instruments, 5,000 holdings, and 250 trading days of prices; allow scale to be parameterized. |
| NFR-10 | Auditability           | Preserve immutable historical records or append-only events for material decisions and state changes.                                                                         |
| NFR-11 | Reproducibility        | Use a documented fixed seed for synthetic data; repeated runs must match in row counts/checksums.                                                                             |
| NFR-12 | Maintainability        | Document data dictionary, IDs, relationships, policy assumptions, evaluation logic, and validation rules.                                                                     |
| NFR-13 | Explainability         | Clearly expose drift, policy decisions, trade rationales, fees, post-trade effects, and exceptions.                                                                           |
| NFR-14 | Lawful provenance      | If external data is used, document source, license/terms, retrieval date, attribution, and transformations.                                                                   |
| NFR-15 | Account security       | Use Django password hashing, session management, CSRF protection, server-side form validation, and access controls; do not store plaintext passwords.                         |
| NFR-16 | Registration integrity | Enforce username and email uniqueness at the persistence layer as well as in debounced checks and form submission.                                                            |

## 6. Inputs

### Account and profile inputs

- **Registration:** Username, email, password, first name, last name (required); phone number (optional).
- **Availability checks:** Username and email submitted separately after individual debounce intervals.
- **Login:** Username or email, and password.
- **Profile update:** Editable account fields, optional phone number, and linked investor risk profile; specific risk-profile values and edit governance are pending.

### 6.1 Request inputs

| Input                                 | Purpose                                                    | Required?                                                   |
| ------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------- |
| Portfolio identifier                  | Identifies portfolio to evaluate                           | Yes                                                         |
| Requesting user/authorization context | Determines permitted access                                | Yes                                                         |
| Evaluation as-of date                 | Determines applicable holdings, targets, and prices        | Yes; may default to current date by explicit product policy |
| Generate proposal flag                | Separates evaluation-only from proposal-requested behavior | Yes                                                         |
| Policy/configuration reference        | Selects applicable eligibility and constraint rules        | Yes; may be resolved from active configuration              |

### 6.2 Domain data inputs

- **InvestorProfile:** Investor identifier and risk profile.
- **Portfolio:** Portfolio identifier, ownership, and relevant state.
- **Instrument:** Instrument identifier and asset-class classification.
- **Holding:** Portfolio-to-instrument position and quantity, valid as of the evaluation.
- **MarketPrice:** Instrument price, date/time, and currency/units where applicable.
- **TargetAllocation:** Target weights by asset class and effective date.
- **Constraint:** Minimum trade sizes, excluded instruments, liquidity restrictions, and other applicable policy restrictions.
- **FeeSchedule:** Applicable fee tiers, rates, and effective dates.
- **Trade:** Existing trade/event history where needed to reconstruct holdings; proposed trades are outputs.

The original problem statement identifies these entities along with **RebalanceProposal**. Their exact fields, cardinalities, and lifecycle statuses must be defined in a separate data dictionary/schema.

### 6.3 Derived calculation inputs

- Holding market value = quantity × applicable unit price.
- Portfolio market value = sum of included holding market values (plus cash if explicitly modeled).
- Current asset-class weight = asset-class market value ÷ total portfolio market value × 100%.
- Allocation drift (percentage points) = current weight − target weight.

**Confirmed funding rule:** No new cash is added. Estimated buy costs and all transaction fees reduce portfolio cash; sale proceeds increase cash available to fund purchases and fees. **Still open:** How portfolio cash is represented, currency handling, fee tiers, and trade rounding.

## 7. Outcomes and outputs

**Account outcomes:** Successful registration creates an account; duplicates or invalid inputs produce field-specific errors. Successful login creates a Django-authenticated session and opens the dashboard; invalid credentials produce a generic error. Profile view displays account and investor risk details; successful edits persist validated changes, while rejected edits preserve existing values.

| Outcome                                                 | Meaning                                                                                                                                                              | Saved information                                                                                                                      |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Evaluation completed — no proposal requested** | Current allocation and drift were computed; no trading recommendation was attempted.                                                                                 | Valuation, weights, drift, input references, evaluation status.                                                                        |
| **No rebalancing needed**                         | All asset-class drifts are already within ±2 percentage points, even if a proposal was explicitly requested.                                                        | Evaluation, no-rebalance message, policy decision, status.                                                                             |
| **Within safe limit — rebalancing optional**     | All drifts are within ±5 points, but at least one exceeds ±2 points. Show safe-limit message; proceed with a proposal only on explicit request.                    | Evaluation, safe-limit message, request decision, and proposal if requested and feasible.                                              |
| **Proposal awaiting investor confirmation**       | Explicitly requested candidate trades passed checks, post-trade drifts meet ±2 points, and estimated costs have been displayed.                                     | Proposed buys/sells, estimated fees, cash effects, expected holdings/weights, remaining drift, validation results, confirmation state. |
| **No feasible proposal**                          | Funding or other constraints prevent a compliant trade set; an insufficient-cash simulation is rolled back with the exact message "No enough cash available to buy". | Evaluation, attempted decision/constraint findings, reason, rollback outcome, status.                                                  |
| **Evaluation exception**                          | Missing/stale/invalid data or another blocking condition prevents a reliable result.                                                                                 | Identified issues, affected records, severity, status, and available partial diagnostics.                                              |

### Expected evaluation report

Each completed evaluation should make available:

1. Portfolio ID, evaluation ID, requester, as-of date, and timestamp.
2. Total portfolio value and current allocation by asset class.
3. Target weights, current weights, and signed drift in percentage points.
4. Whether a proposal was requested; ±5-point safe-limit status; ±2-point rebalancing eligibility; and any required messages.
5. If proposed: buy/sell instruments, quantities/values, estimated fees, cash funding, instrument-level minimum-trade checks, simulated post-trade allocation, and investor confirmation request/state.
6. Exceptions, assumptions, policy version, and traceable source references.
7. Review status and historical events, where applicable.

## 8. Synthetic data and acceptance requirements

The supplied problem statement requires a reproducible educational dataset and validation evidence. The data-generation workstream must:

- Define a data dictionary for the ten named core entities, including types, required fields, allowed values, units, uniqueness, and validation rules.
- Generate parent/master records before dependent holdings, prices, trades, and proposal/event records; use immutable deterministic IDs and consistent foreign keys.
- Target 1,000 portfolios, 2,000 instruments, 5,000 holdings, and 250 trading days of prices, with a smaller parameterized starter scale.
- Include normal cases and labeled anomalies: weights not summing to 100%, trades exceeding holdings, excluded instruments recommended, omitted fees, and unflagged stale prices; also cover missing prices, high drift, liquidity restrictions, and fee tiers.
- Derive expected outcomes from documented rules, not random independent labels; store labels in a separate `ground_truth.csv` or `ground_truth.json`, not as input features.
- Validate referential integrity, lifecycle/date consistency, arithmetic reconciliation, and duplicate records.
- Export CSV/JSON/SQL seeds as applicable, schema/data dictionary, generator instructions, fixed seed, source manifest, and validation summary.
- Regenerate twice with the same seed and verify matching row counts/checksums.

### Acceptance checks

- Target weights reconcile to 100% for valid baseline cases.
- Current and simulated weights reconcile with corresponding holdings and prices.
- Proposed trades do not violate minimum size, available holdings, exclusions, or liquidity policy.
- Estimated fees match the effective fee schedule.
- Invalid cases are identified and recorded rather than silently accepted.
- Fixed-seed datasets and ground-truth outcomes are reproducible.

## 9. Decisions requiring clarification (not yet confirmed)

The following decisions are deliberately **open** and must not be silently assumed:

1. **Instrument exclusions:** Are excluded instruments prohibited for both buys and sells, or only for new purchases?
2. **Invalid or unavailable prices:** When no acceptable price exists within the previously agreed price-freshness window (latest stored price may be up to two previous trading sessions old), should evaluation stop or continue with warnings/partial results?
3. **Proposal lifecycle:** What review statuses and actions should saved proposals support, and which roles may perform them?
4. **Target allocation changes:** Should existing proposals retain the target-allocation version used at creation or become invalid when targets change?
5. **Partially successful allocation:** If constraints prevent reaching ±2 points for every asset class, may an improved but still outside-tolerance proposal be considered valid, or must it be rejected?
6. **Concurrent data changes:** Should an evaluation use its initial input snapshot throughout, or refresh inputs when holdings or prices change mid-evaluation?

### Account-specific details awaiting agreement

- Allowed risk-profile values and whether investors may change risk classification directly or require approval.
- Whether registration automatically creates/links an `InvestorProfile`, and the process for linking portfolios.
- Exact debounce interval, password policy, email verification, and account recovery requirements.

### Implementation details also awaiting agreement

- Cash representation within portfolio valuation and asset-class weights; ordering of proposed sales/buys and fee debits.
- Exact fee schedules, minimum trade quantity/value units, rounding, and liquidity measurement.
- Detailed authorization for confirmation and review, as well as operational response-time and retention targets.

**Previously agreed price-freshness rule:** Use the latest stored price if it is from the current or either of the two preceding trading sessions; the behavior when none is available remains unresolved.

---

**Basis:** Supplied *Problem Statement.docx*, agreed on-demand workflow, prior project discussions (Django, 1,000 portfolios, 2,000 instruments, 5,000 holdings, 250 trading days, two-session price fallback), and newly confirmed decisions 1–6. All remaining decisions are explicitly open.
