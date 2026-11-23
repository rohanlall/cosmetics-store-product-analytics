-- Brands whose products are most often removed from carts (HogQL, PostHog SQL editor)
SELECT
    properties.brand AS brand,
    countIf(event = 'added_to_cart')      AS cart_adds,
    countIf(event = 'removed_from_cart')  AS removals,
    round(removals / cart_adds, 2)        AS removals_per_add,
    countIf(event = 'purchase_completed') AS purchases
FROM events
WHERE properties.source = 'kaggle_cosmetics' AND properties.brand IS NOT NULL
GROUP BY brand
HAVING cart_adds >= 500
ORDER BY removals_per_add DESC
LIMIT 15
