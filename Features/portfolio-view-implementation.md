# Portfolio and target allocation implementation

Implemented from `portfolio_view.md` and `latest_market_price_rules.md`. `SPEC.md` is unchanged.

## Pages and behavior

- `/portfolio/` (`my_portfolio`): authenticated investor's single linked portfolio, name, cash, holdings, instrument/symbol, asset class, currency, quantity, average cost, latest valid closing price/date, and market value.
- `/target-allocation/` (`target_allocation`): authenticated investor's complete current allocation, including supported asset classes with no holdings; initial setup when no version exists.
- Both pages are linked from dashboard and main navigation. They use the existing design, session protection, `never_cache`, CSRF protection, and protected history restoration handler.
- An account without a portfolio sees an explanatory empty state; no portfolio or holdings are created automatically.

## Price selection and valuation

`portfolio_valuation()` uses correlated `Subquery`/`OuterRef` expressions for closing price and price date. Price candidates are from the existing `TradePrice` model/table (`trade_prices`), match the held instrument, have a positive non-null closing price, and have `price_date <= timezone.localdate()`. They are ordered by descending price date and price ID. Null and future prices do not obscure an earlier valid price.

This follows the dedicated My Portfolio price-selection rules: no age cutoff is applied here. The separate evaluation freshness policy in SPEC.md is not implemented by this portfolio display feature. Each price date is displayed explicitly.

Holdings and instrument/asset-class details are retrieved in one query, independently of holding count. Calculations use Decimal with sufficient precision for multiplication. Total holdings market value excludes cash and holdings without valid prices; missing prices are flagged and totals are labeled partial. Zero prices are not substituted for unavailable prices. Cash is displayed separately. Existing instrument data is entirely INR; currency conversion is not added.

## Allocation validation and history

- Percentages use Decimal, accept at most four decimal places per the existing model, must each be within 0–100, and must total exactly 100.
- Duplicate, omitted, unknown, and malformed asset-class submissions are rejected. Every configured asset class appears once in the normal UI.
- A single transaction obtains `select_for_update()` on the owned portfolio row, revalidates the complete allocation, compares it with the latest committed snapshot, and allocates the next version.
- Each actual change inserts a complete snapshot, including zero values and unchanged asset-class percentages, before updating `Portfolio.current_allocation_version` atomically. No earlier rows are edited or removed.
- Identical submissions create no version and do not update portfolio timestamps. Concurrent identical submissions create one version; concurrent distinct submissions produce serialized complete versions.
- Existing `(portfolio, version_number, asset_class)` database uniqueness is reused.
- Portfolio identifiers supplied through extra query/form parameters cannot select another user's data. The save service also checks ownership under its lock.

## Migration

`0009_portfolio_current_allocation_version` adds `Portfolio.current_allocation_version` (0 means no saved allocation) and initializes each portfolio from its highest existing allocation version. Existing allocation history is not modified.

Applied successfully to the existing database. Before/after comparisons preserved every existing field across 1,000 portfolios, 5,000 holdings, 2,000 instruments, 5 asset classes, 10,000 market prices, 1,000 investor profiles, and 1,000 users. There were no existing target allocation records to change. A dedicated test verifies backfill from existing historical versions.

## Files

Modified:

- `myapp/models.py`: portfolio current version number.
- `myapp/views.py`: owned portfolio and allocation views.
- `myapp/urls.py`: page routes.
- `myapp/templates/myapp/base.html`: navigation and save-result messages.
- `myapp/templates/myapp/dashboard.html`: feature links.
- `myapp/static/myapp/styles.css`: responsive holdings table, allocation form, and portfolio cards.

Created:

- `myapp/portfolio_services.py`: price selection, Decimal valuation, validation, and serialized snapshot saving.
- `myapp/allocation_forms.py`: complete-allocation formset.
- `myapp/templates/myapp/portfolio.html`.
- `myapp/templates/myapp/target_allocation.html`.
- `myapp/templates/myapp/_no_portfolio.html`.
- `myapp/migrations/0009_portfolio_current_allocation_version.py`.
- `myapp/test_portfolio.py`.
- `Requirements/portfolio-view-implementation.md`.

## Verification and scope

Results: all 45 Django tests passed, including real MySQL concurrency checks. Django system checks passed, and the migration drift check reported no changes.

Run from the Django project directory:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test myapp --noinput
```

Portfolio tests cover owner isolation, login requirements, read-only holdings, exact Decimal calculations, null/future/older price selection, missing prices, empty and unlinked portfolios, constant query count, and dashboard navigation.

Allocation tests cover initial creation, complete immutable snapshots, latest-version display, unchanged submissions, exact totals, boundary percentages, invalid decimals, duplicate/missing/unknown classes, malformed management data, CSRF, ownership, database uniqueness, rollback during both insertion and reference update, historical version backfill, and real concurrent MySQL saves. Existing authentication/profile tests also run.

Proposal invalidation and its tests are not applicable: `RebalanceProposal` is commented out, and SPEC.md leaves target-change proposal governance undecided. No proposal model, evaluation, drift, rebalancing, holding editing, external price API, or frontend framework was added.
