"""Product analytics pipeline: Kaggle cosmetics-shop events -> DuckDB -> SQL metrics -> results.json

Usage:  python analysis.py [path/to/events.csv]
"""
import sys, json, glob, time
import duckdb

csv = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("data/*.csv"))[0]
t0 = time.time()
con = duckdb.connect("data/events.duckdb")

print(f"Loading {csv} ...")
con.execute(f"""
CREATE OR REPLACE TABLE events AS
SELECT CAST(event_time AS TIMESTAMP) AS ts,
       event_type, product_id, category_code, NULLIF(brand,'') AS brand,
       price, user_id, user_session
FROM read_csv_auto('{csv}', header=true)
""")

def q(sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, [v.isoformat() if hasattr(v, "isoformat") else v for v in row])) for row in cur.fetchall()]

R = {"source": csv.replace("\\", "/").split("/")[-1]}

R["overview"] = q("""
SELECT COUNT(*) events, COUNT(DISTINCT user_id) users, COUNT(DISTINCT user_session) sessions,
       COUNT(DISTINCT product_id) products,
       COUNT(*) FILTER (WHERE event_type='purchase') purchases,
       ROUND(SUM(price) FILTER (WHERE event_type='purchase'),2) revenue,
       COUNT(DISTINCT user_id) FILTER (WHERE event_type='purchase') buyers,
       MIN(ts)::DATE start_date, MAX(ts)::DATE end_date
FROM events""")[0]

R["event_mix"] = q("SELECT event_type, COUNT(*) n FROM events GROUP BY 1 ORDER BY 2 DESC")

# User-level funnel: view -> cart -> purchase (purchase must follow a cart)
R["funnel"] = q("""
WITH u AS (
  SELECT user_id,
    MIN(ts) FILTER (WHERE event_type='view')     v,
    MIN(ts) FILTER (WHERE event_type='cart')     c,
    MAX(ts) FILTER (WHERE event_type='purchase') p
  FROM events GROUP BY 1)
SELECT COUNT(v) viewed, COUNT(c) carted, COUNT(*) FILTER (WHERE c IS NOT NULL AND p >= c) purchased FROM u""")[0]

# Session-level funnel
R["session_funnel"] = q("""
WITH s AS (SELECT user_session,
  BOOL_OR(event_type='view') v, BOOL_OR(event_type='cart') c, BOOL_OR(event_type='purchase') p
  FROM events WHERE user_session IS NOT NULL GROUP BY 1)
SELECT COUNT(*) sessions, COUNT(*) FILTER (WHERE v) viewed, COUNT(*) FILTER (WHERE c) carted,
       COUNT(*) FILTER (WHERE p) purchased FROM s""")[0]

R["daily"] = q("""
SELECT ts::DATE AS day, COUNT(DISTINCT user_id) dau, COUNT(DISTINCT user_session) sessions,
       COUNT(*) FILTER (WHERE event_type='purchase') purchases,
       ROUND(SUM(price) FILTER (WHERE event_type='purchase'),2) revenue
FROM events GROUP BY 1 ORDER BY 1""")

R["hourly"] = q("""
SELECT HOUR(ts) AS hour, COUNT(*) events,
       COUNT(*) FILTER (WHERE event_type='purchase') purchases
FROM events GROUP BY 1 ORDER BY 1""")

# Weekly cohort retention (week of first activity -> active in later weeks)
R["retention"] = q("""
WITH a AS (SELECT DISTINCT user_id, DATE_TRUNC('week', ts)::DATE wk FROM events),
f AS (SELECT user_id, MIN(wk) cohort FROM a GROUP BY 1),
j AS (SELECT f.cohort, DATEDIFF('week', f.cohort, a.wk) w, COUNT(DISTINCT a.user_id) n
      FROM a JOIN f USING(user_id) GROUP BY 1,2)
SELECT cohort, w, n, ROUND(100.0*n/MAX(n) FILTER (WHERE w=0) OVER (PARTITION BY cohort),1) pct
FROM j ORDER BY cohort, w""")

R["top_brands"] = q("""
SELECT brand, COUNT(*) FILTER (WHERE event_type='view') views,
       COUNT(*) FILTER (WHERE event_type='purchase') purchases,
       ROUND(SUM(price) FILTER (WHERE event_type='purchase'),2) revenue,
       ROUND(100.0*COUNT(*) FILTER (WHERE event_type='purchase')/NULLIF(COUNT(*) FILTER (WHERE event_type='view'),0),2) view_to_buy
FROM events WHERE brand IS NOT NULL GROUP BY 1 ORDER BY revenue DESC NULLS LAST LIMIT 10""")

R["top_products"] = q("""
SELECT product_id, ANY_VALUE(brand) brand, ROUND(AVG(price),2) price,
       COUNT(*) FILTER (WHERE event_type='view') views,
       COUNT(*) FILTER (WHERE event_type='cart') carts,
       COUNT(*) FILTER (WHERE event_type='purchase') purchases,
       ROUND(SUM(price) FILTER (WHERE event_type='purchase'),2) revenue
FROM events GROUP BY 1 ORDER BY revenue DESC NULLS LAST LIMIT 10""")

R["most_abandoned"] = q("""
SELECT product_id, ANY_VALUE(brand) brand, ROUND(AVG(price),2) price,
       COUNT(*) FILTER (WHERE event_type='cart') carts,
       COUNT(*) FILTER (WHERE event_type='remove_from_cart') removes,
       COUNT(*) FILTER (WHERE event_type='purchase') purchases
FROM events GROUP BY 1 HAVING carts >= 200
ORDER BY removes*1.0/carts DESC LIMIT 10""")

R["price_bands"] = q("""
SELECT CASE WHEN price<5 THEN '<$5' WHEN price<10 THEN '$5-10' WHEN price<20 THEN '$10-20'
            WHEN price<50 THEN '$20-50' ELSE '$50+' END band,
       MIN(price) mn,
       COUNT(*) FILTER (WHERE event_type='view') views,
       COUNT(*) FILTER (WHERE event_type='purchase') purchases,
       ROUND(100.0*COUNT(*) FILTER (WHERE event_type='purchase')/NULLIF(COUNT(*) FILTER (WHERE event_type='view'),0),2) conv
FROM events WHERE price > 0 GROUP BY 1 ORDER BY mn""")

R["sessions"] = q("""
WITH s AS (SELECT user_session, COUNT(*) n, DATEDIFF('second', MIN(ts), MAX(ts)) dur,
           BOOL_OR(event_type='purchase') bought FROM events WHERE user_session IS NOT NULL GROUP BY 1)
SELECT bought, COUNT(*) sessions, ROUND(AVG(n),1) avg_events,
       ROUND(MEDIAN(dur)/60.0,1) median_minutes FROM s GROUP BY 1 ORDER BY 1""")

R["customers"] = q("""
WITH b AS (SELECT user_id, COUNT(DISTINCT user_session) orders, SUM(price) spend
           FROM events WHERE event_type='purchase' GROUP BY 1)
SELECT CASE WHEN orders=1 THEN 'One-time' WHEN orders<=3 THEN '2-3 orders' ELSE '4+ orders' END segment,
       COUNT(*) customers, ROUND(SUM(spend),2) revenue, ROUND(AVG(spend),2) avg_spend
FROM b GROUP BY 1 ORDER BY MIN(orders)""")

R["aov"] = q("""
SELECT ROUND(AVG(v),2) aov, ROUND(MEDIAN(v),2) median_basket, ROUND(AVG(items),1) avg_items FROM
(SELECT user_session, SUM(price) v, COUNT(*) items FROM events WHERE event_type='purchase' GROUP BY 1)""")[0]

with open("results.json", "w") as f:
    json.dump(R, f, default=str, indent=1)
print(f"Done in {time.time()-t0:.1f}s -> results.json")
print(json.dumps(R["overview"], default=str, indent=1))
