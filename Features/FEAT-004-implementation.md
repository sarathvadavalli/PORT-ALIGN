# FEAT-004 implementation

## Confirmed policy choices

- Recommend considering rebalancing only when at least one absolute drift exceeds 5 percentage points.
- Permit the sample rebalancing request when at least one absolute drift exceeds 2 points, including portfolios within the 5-point safe limit.
- Reuse the existing latest historical closing-price lookup. Price dates remain visible.
- SPEC.md and the feature instructions are unchanged.

## Functionality and specification mapping

| Requirement                                           | Implementation                                                                                                                                                                                                                                                                                       |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FEAT-004 retrieval; SPEC FR-02/FR-23, NFR-05          | My Portfolio still queries only the authenticated investor's portfolio. The sample action also resolves ownership on the server.                                                                                                                                                                     |
| FEAT-004 calculations; SPEC FR-05/FR-06, NFR-01       | `portfolio_allocation_valuation()` reuses priced holdings, aggregates market values by asset class, and calculates current percentages and signed percentage-point drift with Decimal precision 64. Cash is excluded, as specified by the holdings-only formula.                                   |
| Latest target version                                 | Read the snapshot selected by the portfolio's committed `current_allocation_version`. Validate its completeness, allowed percentages, and exact 100% total before comparing drift.                                                                                                                 |
| All supported asset classes                           | Include classes with no holdings at zero market value and 0% current allocation.                                                                                                                                                                                                                     |
| FEAT-004 missing/empty/zero cases; SPEC FR-04, NFR-07 | Missing prices block the complete allocation comparison, name the instruments, and suppress chart/rebalancing. Empty and zero-value portfolios receive explicit messages without division. Missing/invalid targets permit current-weight display but suppress drift and rebalancing until corrected. |
| FEAT-004 messages/colors; SPEC FR-07/FR-19            | Inclusive ±2 is blue; above +2 is amber; below −2 is plum. Recommendation requires strictly more than ±5. Within ±5, use the exact balanced message and explain optional rebalancing when any drift exceeds ±2. Decisions use unrounded values.                                                 |
| FEAT-004 chart                                        | Responsive SVG doughnut with asset-class color keys, accessible title/description, and a numeric comparison table. No chart dependency or frontend framework.                                                                                                                                        |
| FEAT-004 sample action; SPEC on-demand boundary       | POST `/portfolio/rebalance/` is a placeholder only. It recalculates current eligibility and returns plain-text HttpResponse; no proposals, trades, or records are created.                                                                                                                         |
| NFR-15                                                | Retain Django login/session, CSRF, no-store headers, and protected-history behavior.                                                                                                                                                                                                                 |

The existing holdings table retains its explicitly labeled partial total for browsing, as defined by FEAT-002/003. It is never used as a complete valuation for the new allocation chart, drift analysis, or rebalancing eligibility when any price is missing.

## Files changed

- `myapp/portfolio_services.py`: reusable read-only allocation service; reuse existing price selection and validation.
- `myapp/views.py`: attach the valuation to My Portfolio; add protected POST-only sample response.
- `myapp/urls.py`: sample route.
- `myapp/templates/myapp/portfolio.html`: include the valuation section.
- `myapp/templates/myapp/_valuation.html`: chart, comparison table, messages, refresh link, and sample request form.
- `myapp/static/myapp/styles.css`: responsive chart/comparison layout and drift colors.
- `myapp/test_valuation.py`: feature tests.
- `Features/FEAT-004-implementation.md`: decisions and verification record.

## Verification

Executed from the Django project directory:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test myapp --noinput --verbosity 1
```

All **58 tests passed**, including the 13 new valuation tests and existing authentication, portfolio, allocation, and concurrency tests. Django system checks passed; no schema changes were detected. No migrations were introduced or applied.

New tests verify aggregation of multiple instruments per class, exact totals/current weights, unheld classes, latest targets, ±2/±5 boundaries and adjacent Decimal values, missing prices, empty/zero portfolios, missing/invalid targets, dynamic recalculation, constant query count, SELECT-only service execution, UI chart/colors/messages, authentication/ownership, CSRF, POST-only sample behavior, live eligibility rechecks, and unchanged financial records after the sample request.

Full successful allocation comparison uses three queries independent of holding count: priced holdings with related instrument/asset class, supported asset classes, and current targets. The page reuses the already-loaded holdings result.

No proposal generation, buy/sell advice, execution, valuation persistence, new tables, external price calls, or dependency changes were added. The only financial-policy deviation from SPEC.md is the explicitly confirmed historical-price policy described above. Browser rendering was checked through Django response tests; no automated visual browser test was run.
