"""Smart Inventory Dashboard.   Run:  python -m streamlit run app.py
(first run `python main.py all` once so the database and model exist)"""
import streamlit as st

from src import dashboard_data as dd
from src import database as db

st.set_page_config(page_title="Smart Inventory", page_icon="📦", layout="wide")

STATUS_COLOR = {"CRITICAL": "#ffb3b3", "REORDER": "#ffd9a0", "OK": "#c8f2c8", "OVERSTOCK": "#b9d7f5"}
STATUS_ORDER = list(STATUS_COLOR)

st.markdown("""
<style>
.block-container {padding-top: 3.5rem;}
.hero {background: linear-gradient(90deg,#1f4e79,#2e86c1); padding: 18px 26px;
       border-radius: 14px; margin-bottom: 14px;}
.hero h1 {margin: 0; font-size: 1.8rem; color: #fff;}
.hero p {margin: 4px 0 0; color: #e8f1fa;}
div[data-testid="stMetric"] {background: var(--secondary-background-color);
       border: 1px solid rgba(128,128,128,.25); border-radius: 12px;
       padding: 14px 18px; box-shadow: 0 1px 4px rgba(0,0,0,.08);}
button[data-baseweb="tab"] {font-size: 1.02rem; font-weight: 600;}
</style>
<div class="hero"><h1>📦 Smart Inventory Management</h1>
<p>ML demand forecasting &nbsp;•&nbsp; Reorder planning &nbsp;•&nbsp; SQL analytics</p></div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
def color_status(row):
    return [f"background-color: {STATUS_COLOR.get(row['status'], 'white')}; color: black"] * len(row)


def show_chart(builder, fallback, *args):
    """Draw an Altair chart; if anything goes wrong fall back to a simple native chart."""
    try:
        from src import charts
        st.altair_chart(getattr(charts, builder)(*args))
    except Exception:
        fallback()


@st.cache_data(ttl=300)
def load_plan():
    return dd.plan()


try:
    plan_all = load_plan()
    if plan_all.empty:
        raise ValueError("empty")
except Exception:
    st.error("Database is empty. Open a terminal in this folder and run:  python main.py all")
    st.stop()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("🔎 Filters")
    all_cats = sorted(plan_all["category"].unique())
    cats = st.multiselect("Category", all_cats, default=all_cats)
    st.divider()
    st.caption(f"🕒 Plan generated: {dd.last_updated()}")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Tip: to rebuild everything with fresh data run `python main.py all`.")

plan = plan_all[plan_all["category"].isin(cats)]
if plan.empty:
    st.warning("Select at least one category in the sidebar.")
    st.stop()

tab_over, tab_plan, tab_fc, tab_model, tab_sql = st.tabs(
    ["📊 Overview", "📋 Reorder Plan", "📈 Demand Forecast", "🤖 Model Performance", "🗄️ SQL Analytics"])

# ------------------------------------------------------------------ Overview
with tab_over:
    counts = plan["status"].value_counts()
    k = st.columns(5)
    k[0].metric("📦 Products", len(plan))
    k[1].metric("🔴 Critical", int(counts.get("CRITICAL", 0)))
    k[2].metric("🟠 Reorder", int(counts.get("REORDER", 0)))
    k[3].metric("🔵 Overstock", int(counts.get("OVERSTOCK", 0)))
    k[4].metric("💰 Order budget", f"{plan['est_order_cost'].sum():,.0f}")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Revenue trend (all products)")
        days = st.slider("Days to show", 30, 365, 180, step=30)
        rev = dd.daily_revenue(days)
        show_chart("revenue_chart", lambda: st.line_chart(rev), rev)
    with right:
        st.subheader("Products by status")
        show_chart("status_chart", lambda: st.bar_chart(counts), plan)

    st.subheader("Stock cover vs supplier lead time")
    st.caption("Black tick = supplier lead time. If the bar is shorter than the tick, "
               "the product will run out before a new order can arrive.")
    show_chart("cover_chart", lambda: st.bar_chart(plan.set_index("name")["days_of_cover"]), plan)

    st.subheader("⚠️ Needs action now")
    urgent = plan[plan["status"].isin(["CRITICAL", "REORDER"])].drop(columns="product_id")
    if urgent.empty:
        st.success("No urgent orders. 🎉")
    else:
        st.dataframe(urgent.style.apply(color_status, axis=1), hide_index=True)

# --------------------------------------------------------------- Reorder Plan
with tab_plan:
    st.subheader("Replenishment plan")
    statuses = st.multiselect("Status", STATUS_ORDER, default=STATUS_ORDER)
    view = plan[plan["status"].isin(statuses)].drop(columns="product_id")
    m = st.columns(3)
    m[0].metric("Products shown", len(view))
    m[1].metric("Units to order", int(view["recommended_qty"].sum()))
    m[2].metric("Estimated spend", f"{view['est_order_cost'].sum():,.0f}")
    st.dataframe(view.style.apply(color_status, axis=1), hide_index=True)
    st.download_button("⬇️ Download CSV", view.to_csv(index=False), "reorder_plan.csv", "text/csv")
    with st.expander("ℹ️ How are these numbers calculated?"):
        st.markdown("""
- **Safety stock** = 1.65 × forecast error × √(lead time)  → about 95% service level
- **Reorder point** = forecast demand during lead time + safety stock
- **EOQ** = √(2 × annual demand × order cost ÷ holding cost)
- **CRITICAL**: stock will run out before a new order can arrive
- **Order quantity** = reorder point + EOQ − current stock""")

# ------------------------------------------------------------ Demand Forecast
with tab_fc:
    prods = dd.products()
    prods = prods[prods["category"].isin(cats)]
    labels = (prods["name"] + "  (" + prods["sku"] + ")").tolist()
    c1, c2 = st.columns([2, 1])
    choice = c1.selectbox("Select product", labels)
    days = c2.slider("History days", 30, 365, 90, step=30)
    pid = int(prods.iloc[labels.index(choice)]["product_id"])
    data = dd.history_and_forecast(pid, days)
    show_chart("forecast_chart", lambda: st.line_chart(data, color=["#555555", "#d62728"]), data)

    row = plan[plan["product_id"] == pid].iloc[0]
    m = st.columns(5)
    m[0].metric("Status", row["status"])
    m[1].metric("Current stock", int(row["current_stock"]))
    m[2].metric("Days of cover", row["days_of_cover"])
    m[3].metric("Lead time (days)", int(row["lead_time_days"]))
    m[4].metric("Order now", int(row["recommended_qty"]))

# ---------------------------------------------------------- Model Performance
with tab_model:
    st.subheader("Model comparison (last 60 days hold-out)")
    runs = dd.model_runs()
    show_chart("model_chart", lambda: st.bar_chart(runs.set_index("model_name")["wape_pct"]), runs)
    st.dataframe(runs, hide_index=True)
    st.caption("WAPE = total absolute error ÷ total demand (lower is better). "
               "The naive model repeats last week's sales; ML models must beat it. Green = selected model.")

# -------------------------------------------------------------- SQL Analytics
with tab_sql:
    st.subheader("SQL analytics")
    results = db.run_named_queries()
    name = st.selectbox("Choose a query", list(results), format_func=lambda x: x.replace("_", " ").title())
    st.dataframe(results[name], hide_index=True)
    with st.expander("Show SQL"):
        text = (db.SQL_DIR / "analytics.sql").read_text()
        block = text.split(f"-- name: {name}")[1].split("-- name:")[0].strip()
        st.code(block, language="sql")
