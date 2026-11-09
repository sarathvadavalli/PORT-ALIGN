You are a senior Software developer working on an existing Portfolio Rebalancing System.

Your task is to implement a **Portfolio Valuation** feature that dynamically calculates the investor's total portfolio market value and current allocation percentages by asset class.

Strictly follow `SPEC.md` and reuse the existing Django models, authentication, database schema, and UI conventions.

## 1. Data Retrieval

- Retrieve the portfolio and all holdings belonging to the authenticated investor as defined in `My Portfolio page` of `FEAT-002, 003.md`.
- Retrieve the latest version of portfolio's target allocation details.
- Evaluate the current allocation and drift percentage for each asset class.
- Recommend portfolio rebalancing if **at least one asset class** exceeds the ±5 percentage-point threshold.
- If all asset classes are within tolerance, display "Your portfolio is balanced. No rebalancing is currently required."

## 2. Valuation Calculations

For each holding:

`Market Value = Quantity × Latest Closing Price`

Aggregate holding market values by asset class.

`Total Portfolio Value = Sum of all holding market values`

For each asset class:

`Current Allocation (%) = (Asset Class Market Value / Total Portfolio Value) × 100`

`Drift (%) = Current Allocation (%) - Target Allocation (%)`

Use `Decimal` for all monetary and percentage calculations.

Include supported asset classes with no holdings as 0% when displaying the allocation comparison.

- Positive drift (+): Current allocation exceeds target → Overweight.
- Negative drift (−): Current allocation is below target → Underweight.
- Zero drift: Current allocation matches target.

## 3. Missing Price Handling

- If any held instrument has no valid historical closing price, block the complete portfolio valuation with a valid message.
- Display the names of instruments with missing prices.
- If the portfolio is empty or its total market value is zero, display an appropriate message instead of attempting division.

## 4. Dynamic Calculation

- Calculate valuation dynamically whenever the investor requests it.
- Do not create database tables or records for storing valuation results.
- Do not modify holdings, prices, or target allocations.
- Keep valuation calculations in a reusable service function rather than directly inside the Django view.

## 5. UI Requirements

Provide a **Portfolio Valuation** section accessible through the existing Portfolio page.

Display:

- Asset-class-level market values.
- Current allocation percentages and drift for each asset class.
- If allocation is nearly balanced(drift is within ±2%), show in blue color. If more than +2%, show it in one warning color. If less than -2%, show in another warning color.
- A pie or doughnut chart showing current asset-class allocation.
- A message that indicates whether investor should consider rebalancing or not and a button to initiate rebalancing process. (Add a sample view for button response by returning a message as HTTPResponse)
- Follow the existing UI framework and responsive styling conventions.

## 6. Testing

Test the following scenarios:

- Correct market value for each instrument.
- Correct aggregation of multiple instruments within one asset class.
- Correct total portfolio valuation and allocation percentages.
- Asset classes without holdings.
- Missing closing prices blocking valuation.
- Empty portfolio and zero total portfolio value.
- Unauthorized portfolio access.

## 7. Scope Restrictions

Do not implement:

- Rebalancing proposal generation.
- Buy/sell recommendations.
- Trade execution.
- Valuation history storage.

After implementation, provide a summary of modified files, tests executed, and compliance with `SPEC.md`.

If requirements conflict or essential details are unclear, ask for clarification before implementing.
