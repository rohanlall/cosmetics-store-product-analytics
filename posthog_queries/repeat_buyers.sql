-- Revenue from one-time vs repeat buyers (orders = sessions with a purchase)
SELECT segment, count() AS customers, round(sum(spend), 2) AS revenue, round(avg(spend), 2) AS avg_spend
FROM (
    SELECT distinct_id,
           uniq(properties.$session_id) AS orders,
           sum(toFloat(properties.revenue)) AS spend,
           multiIf(orders = 1, 'One-time', orders <= 3, '2-3 orders', '4+ orders') AS segment
    FROM events
    WHERE event = 'purchase_completed' AND properties.source = 'kaggle_cosmetics'
    GROUP BY distinct_id
)
GROUP BY segment
ORDER BY customers DESC
