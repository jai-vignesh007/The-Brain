import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.cloud import bigquery
from google.oauth2 import service_account
from utils import get_client, render_sidebar

PROJECT = "the-brain-487614"

#--- SIDEBAR (always first) ---
render_sidebar()
client = get_client() 

def run_query(sql):
    return get_client().query(sql).to_dataframe()

# ── Page setup ────────────────────────────────────────────────
st.set_page_config(page_title="Google Ads Performance", page_icon="📊", layout="wide")
st.title("📊 Google Ads Performance")
st.caption("Source: BigQuery · analytics.google_ads_campaign_performance · Auto-refreshes daily")

# ── Load data ─────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data():
    return run_query("""
        SELECT *
        FROM `the-brain-487614.analytics.google_ads_campaign_performance`
        ORDER BY date DESC
    """)

df = load_data()

# fix types
df["date"]        = pd.to_datetime(df["date"])
df["cost_usd"]    = pd.to_numeric(df["cost_usd"],    errors="coerce").fillna(0)
df["clicks"]      = pd.to_numeric(df["clicks"],      errors="coerce").fillna(0)
df["impressions"] = pd.to_numeric(df["impressions"], errors="coerce").fillna(0)
df["conversions"] = pd.to_numeric(df["conversions"], errors="coerce").fillna(0)
df["ctr_pct"]     = pd.to_numeric(df["ctr_pct"],     errors="coerce").fillna(0)
df["cost_per_conversion"] = pd.to_numeric(df["cost_per_conversion"], errors="coerce")

# ── Sidebar filters ───────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    devices    = ["All"] + sorted(df["device"].dropna().unique().tolist())
    sel_device = st.selectbox("Device", devices)
    date_min   = df["date"].min().date()
    date_max   = df["date"].max().date()
    sel_dates  = st.date_input("Date range", value=(date_min, date_max))

fdf = df.copy()
if sel_device != "All":
    fdf = fdf[fdf["device"] == sel_device]
if len(sel_dates) == 2:
    fdf = fdf[
        (fdf["date"].dt.date >= sel_dates[0]) &
        (fdf["date"].dt.date <= sel_dates[1])
    ]

# ── KPI cards ─────────────────────────────────────────────────
total_spend       = fdf["cost_usd"].sum()
total_clicks      = fdf["clicks"].sum()
total_impressions = fdf["impressions"].sum()
total_conversions = fdf["conversions"].sum()
avg_ctr           = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
avg_cpa           = (total_spend / total_conversions) if total_conversions > 0 else 0

k1,k2,k3,k4,k5,k6 = st.columns(6)
k1.metric("Total Spend",       f"${total_spend:,.2f}")
k2.metric("Total Clicks",      f"{int(total_clicks):,}")
k3.metric("Impressions",       f"{int(total_impressions):,}")
k4.metric("Conversions",       f"{int(total_conversions):,}")
k5.metric("Avg CTR",           f"{avg_ctr:.1f}%")
k6.metric("Cost / Conversion", f"${avg_cpa:.2f}" if total_conversions > 0 else "—")

st.divider()

# ── Daily spend vs clicks ─────────────────────────────────────
daily = (
    fdf.groupby("date")
    .agg(cost_usd=("cost_usd","sum"), clicks=("clicks","sum"),
         conversions=("conversions","sum"))
    .reset_index()
)

fig1 = go.Figure()
fig1.add_bar(x=daily["date"], y=daily["cost_usd"], name="Spend ($)",
             marker_color="#378ADD")
fig1.add_scatter(x=daily["date"], y=daily["clicks"], name="Clicks", yaxis="y2",
                 line=dict(color="#1D9E75", width=2), mode="lines+markers")
fig1.update_layout(
    title="Daily Spend vs Clicks",
    yaxis=dict(title="Spend ($)"),
    yaxis2=dict(title="Clicks", overlaying="y", side="right"),
    legend=dict(orientation="h", y=1.1),
    height=350, margin=dict(t=50,b=20),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
)
st.plotly_chart(fig1, use_container_width=True)

# ── Device breakdown + conversions ───────────────────────────
c1, c2 = st.columns(2)

with c1:
    dev = fdf.groupby("device").agg(cost_usd=("cost_usd","sum")).reset_index()
    fig2 = px.bar(dev, x="device", y="cost_usd",
                  title="Spend by Device",
                  color_discrete_sequence=["#378ADD"])
    fig2.update_layout(height=320, margin=dict(t=40,b=20),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig2, use_container_width=True)

with c2:
    conv = fdf[fdf["conversions"] > 0].groupby("date").agg(
        conversions=("conversions","sum")
    ).reset_index()
    fig3 = px.bar(conv, x="date", y="conversions", title="Conversions by Day",
                  text="conversions", color_discrete_sequence=["#1D9E75"])
    fig3.update_traces(textposition="outside")
    fig3.update_layout(height=320, margin=dict(t=40,b=20),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── CTR by day of week ────────────────────────────────────────
dow_order = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]
dow = (
    fdf.groupby("day_of_week")
    .agg(clicks=("clicks","sum"), impressions=("impressions","sum"))
    .reset_index()
)
dow["ctr_pct"]     = (dow["clicks"] / dow["impressions"] * 100).round(1)
dow["day_of_week"] = pd.Categorical(dow["day_of_week"], categories=dow_order, ordered=True)
dow = dow.sort_values("day_of_week")

fig4 = px.bar(dow, x="day_of_week", y="ctr_pct", title="CTR % by Day of Week",
              text="ctr_pct", color_discrete_sequence=["#7F77DD"])
fig4.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig4.update_layout(height=300, margin=dict(t=40,b=20), yaxis_title="CTR %",
                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ── Raw data ──────────────────────────────────────────────────
with st.expander("View raw data"):
    st.dataframe(
        fdf.sort_values("date", ascending=False),
        use_container_width=True,
        hide_index=True
    )