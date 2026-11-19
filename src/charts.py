"""Altair chart builders (Altair ships with Streamlit). No Streamlit imports here."""
import altair as alt
import pandas as pd

STATUS_ORDER = ["CRITICAL", "REORDER", "OK", "OVERSTOCK"]
STATUS_COLORS = {"CRITICAL": "#e53935", "REORDER": "#fb8c00", "OK": "#43a047", "OVERSTOCK": "#1e88e5"}
_STATUS_SCALE = alt.Scale(domain=STATUS_ORDER, range=[STATUS_COLORS[s] for s in STATUS_ORDER])


def revenue_chart(rev: pd.DataFrame):
    d = rev.reset_index()
    d.columns = ["date", "revenue"]
    return (alt.Chart(d).mark_area(line={"color": "#1e88e5"}, color="#1e88e5", opacity=0.25)
            .encode(x=alt.X("date:T", title=None), y=alt.Y("revenue:Q", title="Daily revenue"),
                    tooltip=[alt.Tooltip("date:T"), alt.Tooltip("revenue:Q", format=",.0f")])
            .properties(height=300))


def status_chart(plan: pd.DataFrame):
    d = pd.DataFrame({"status": STATUS_ORDER,
                      "products": [int((plan["status"] == s).sum()) for s in STATUS_ORDER]})
    base = alt.Chart(d).encode(x=alt.X("status:N", sort=STATUS_ORDER, title=None, axis=alt.Axis(labelAngle=0)),
                               y=alt.Y("products:Q", title="Products"))
    bars = base.mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
        color=alt.Color("status:N", scale=_STATUS_SCALE, legend=None),
        tooltip=["status:N", "products:Q"])
    labels = base.mark_text(dy=-8, fontWeight="bold").encode(text="products:Q")
    return (bars + labels).properties(height=300)


def cover_chart(plan: pd.DataFrame):
    d = plan.copy()
    d["cover"] = d["days_of_cover"].clip(upper=120)
    order = d.sort_values("cover", ascending=False)["name"].tolist()
    y = alt.Y("name:N", sort=order, title=None)
    bars = alt.Chart(d).mark_bar().encode(
        x=alt.X("cover:Q", title="Days of stock cover (capped at 120)"), y=y,
        color=alt.Color("status:N", scale=_STATUS_SCALE, title="Status"),
        tooltip=["name:N", "status:N", "days_of_cover:Q", "lead_time_days:Q", "current_stock:Q"])
    ticks = alt.Chart(d).mark_tick(color="black", thickness=3, size=16).encode(
        x="lead_time_days:Q", y=y, tooltip=[alt.Tooltip("lead_time_days:Q", title="Supplier lead time")])
    return (bars + ticks).properties(height=max(300, 24 * len(d)))


def forecast_chart(df: pd.DataFrame):
    d = df.reset_index()
    d = d.rename(columns={d.columns[0]: "date"}).melt("date", var_name="series", value_name="units").dropna()
    line = alt.Chart(d).mark_line(strokeWidth=2).encode(
        x=alt.X("date:T", title=None), y=alt.Y("units:Q", title="Units per day"),
        color=alt.Color("series:N", title=None,
                        scale=alt.Scale(domain=["Actual", "Forecast"], range=["#555555", "#e53935"])),
        strokeDash=alt.StrokeDash("series:N", legend=None,
                                  scale=alt.Scale(domain=["Actual", "Forecast"], range=[[1, 0], [6, 3]])),
        tooltip=["date:T", "series:N", alt.Tooltip("units:Q", format=".1f")])
    return line.properties(height=340).interactive()


def model_chart(runs: pd.DataFrame):
    order = runs.sort_values("wape_pct")["model_name"].tolist()
    base = alt.Chart(runs).encode(y=alt.Y("model_name:N", sort=order, title=None),
                                  x=alt.X("wape_pct:Q", title="WAPE % (lower is better)"))
    bars = base.mark_bar().encode(
        color=alt.condition(alt.datum.is_selected == 1, alt.value("#43a047"), alt.value("#9e9e9e")),
        tooltip=["model_name:N", "wape_pct:Q", "mae:Q", "rmse:Q", "r2:Q"])
    labels = base.mark_text(align="left", dx=4).encode(text="wape_pct:Q")
    return (bars + labels).properties(height=180)
