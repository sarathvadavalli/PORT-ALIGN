
#### **Market Price Selection and Portfolio Valuation**

The My Portfolio page must retrieve the latest available closing market price of every instrument held by the authenticated investor.

1. **Data source**

* Use the existing trade_price table as the authoritative source for historical instrument market prices.
* Inspect the existing TradePrice model and identify the actual field names representing the instrument, trading date, and closing price.
* Do not introduce a new market-price table or duplicate price information in the Holding model.
* Do not call external market-price APIs. Prices must be retrieved from the existing database.

2. **Latest closing price selection**

* Use an efficient Django ORM query to retrieve the latest closing price for every held instrument from trade_price table.
* A correlated subquery using `Subquery` and `OuterRef`, or another efficient database-supported approach, is preferred.
* Avoid executing a separate database query for every holding (N+1 query problem).

Conceptual SQL:

```sql
SELECT
    h.instrument_id,
    (
        SELECT tp.closing_price
        FROM trade_price tp
        WHERE tp.instrument_id = h.instrument_id
          AND tp.trading_date <= CURRENT_DATE
          AND tp.closing_price IS NOT NULL
        ORDER BY tp.trading_date DESC
        LIMIT 1
    ) AS latest_closing_price
FROM holding h
WHERE h.portfolio_id = %s;
```

This SQL is illustrative. Adapt all field names and the tie-breaking column to the actual schema.
