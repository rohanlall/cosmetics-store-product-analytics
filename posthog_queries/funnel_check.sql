-- Cross-check the funnel against analysis.py (DuckDB): users reaching each step
SELECT
    uniqIf(distinct_id, event = 'product_viewed')     AS viewed,
    uniqIf(distinct_id, event = 'added_to_cart')      AS carted,
    uniqIf(distinct_id, event = 'purchase_completed') AS purchased,
    round(100 * purchased / viewed, 1)                AS view_to_buy_pct
FROM events
WHERE properties.source = 'kaggle_cosmetics'
