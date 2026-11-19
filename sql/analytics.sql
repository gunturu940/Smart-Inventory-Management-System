-- name: top_products_by_revenue
SELECT p.sku, p.name, p.category,
       SUM(s.units_sold)                           AS units,
       ROUND(SUM(s.units_sold * s.unit_price), 0)  AS revenue
FROM sales s JOIN products p USING (product_id)
GROUP BY p.product_id
ORDER BY revenue DESC
LIMIT 10;

-- name: monthly_revenue_with_growth
WITH m AS (
    SELECT substr(sale_date, 1, 7) AS month, SUM(revenue) AS revenue
    FROM v_daily_revenue GROUP BY 1
    HAVING COUNT(*) >= 28          -- ignore the incomplete current month
)
SELECT month,
       ROUND(revenue, 0) AS revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / LAG(revenue) OVER (ORDER BY month), 1) AS mom_growth_pct
FROM m ORDER BY month DESC LIMIT 12;

-- name: abc_classification
WITH rev AS (
    SELECT p.sku, p.name, SUM(s.units_sold * s.unit_price) AS revenue
    FROM sales s JOIN products p USING (product_id)
    GROUP BY p.product_id
), ranked AS (
    SELECT *, SUM(revenue) OVER (ORDER BY revenue DESC)
              / SUM(revenue) OVER () AS cum_share
    FROM rev
)
SELECT sku, name, ROUND(revenue, 0) AS revenue,
       ROUND(100 * cum_share, 1) AS cum_share_pct,
       CASE WHEN cum_share <= 0.80 THEN 'A'
            WHEN cum_share <= 0.95 THEN 'B' ELSE 'C' END AS abc_class
FROM ranked ORDER BY revenue DESC;

-- name: category_performance
SELECT p.category,
       COUNT(DISTINCT p.product_id)                          AS products,
       SUM(s.units_sold)                                     AS units,
       ROUND(SUM(s.units_sold * s.unit_price), 0)            AS revenue,
       ROUND(100.0 * SUM(s.units_sold * (s.unit_price - p.unit_cost))
             / SUM(s.units_sold * s.unit_price), 1)          AS margin_pct
FROM sales s JOIN products p USING (product_id)
GROUP BY p.category ORDER BY revenue DESC;

-- name: promo_uplift
SELECT p.category,
       ROUND(AVG(CASE WHEN s.promo = 1 THEN s.units_sold END), 1) AS avg_units_promo,
       ROUND(AVG(CASE WHEN s.promo = 0 THEN s.units_sold END), 1) AS avg_units_regular,
       ROUND(AVG(CASE WHEN s.promo = 1 THEN s.units_sold END)
           / AVG(CASE WHEN s.promo = 0 THEN s.units_sold END), 2) AS uplift_x
FROM sales s JOIN products p USING (product_id)
GROUP BY p.category;

-- name: stockout_risk
SELECT p.sku, p.name, r.current_stock, ROUND(r.days_of_cover, 1) AS days_cover,
       p.lead_time_days, r.status, r.recommended_qty
FROM reorder_plan r JOIN products p USING (product_id)
WHERE r.status IN ('CRITICAL', 'REORDER')
ORDER BY r.days_of_cover - p.lead_time_days;

-- name: overstock_capital_tied_up
SELECT p.sku, p.name, r.current_stock,
       ROUND(r.days_of_cover, 0)                    AS days_cover,
       ROUND(r.current_stock * p.unit_cost, 0)      AS capital_tied_up
FROM reorder_plan r JOIN products p USING (product_id)
WHERE r.status = 'OVERSTOCK'
ORDER BY capital_tied_up DESC;

-- name: supplier_exposure
SELECT su.name AS supplier, su.lead_time_days,
       COUNT(*)                                       AS products_flagged,
       SUM(r.recommended_qty)                         AS units_to_order,
       ROUND(SUM(r.est_order_cost), 0)                AS spend_needed
FROM reorder_plan r
JOIN products p  USING (product_id)
JOIN suppliers su USING (supplier_id)
WHERE r.recommended_qty > 0
GROUP BY su.supplier_id ORDER BY spend_needed DESC;
