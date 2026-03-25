import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.cloud import bigquery
from utils import get_client, render_sidebar

PROJECT = "the-brain-487614"
client  = bigquery.Client(project=PROJECT)

st.set_page_config(page_title="Google Ads Intelligence", page_icon="🧠", layout="wide")
st.title("🧠 Google Ads Deep Intelligence")
st.caption("Keyword quality · Ad health · Hourly patterns")
#--- SIDEBAR (always first) ---
render_sidebar()

@st.cache_data(ttl=3600)
def load(query):
    return client.query(query).to_dataframe()

df_kw   = load("SELECT * FROM `the-brain-487614.analytics.google_ads_keyword_intelligence`")
df_ad   = load("SELECT * FROM `the-brain-487614.analytics.google_ads_ad_intelligence`")
df_hour = load("SELECT * FROM `the-brain-487614.analytics.google_ads_hourly_intelligence`")

# fix types
df_hour["cost_usd"]   = pd.to_numeric(df_hour["cost_usd"], errors="coerce").fillna(0)
df_hour["clicks"]     = pd.to_numeric(df_hour["clicks"], errors="coerce").fillna(0)
df_hour["impressions"]= pd.to_numeric(df_hour["impressions"], errors="coerce").fillna(0)
df_hour["conversions"]= pd.to_numeric(df_hour["conversions"], errors="coerce").fillna(0)
df_kw["quality_score"]= pd.to_numeric(df_kw["quality_score"], errors="coerce").fillna(0)

# ─────────────────────────────────────────────
# SECTION 1: KEYWORD INTELLIGENCE
# ─────────────────────────────────────────────
st.markdown("## 🔑 Keyword Intelligence — Stupidity Tax")
st.caption("Keywords that are enabled but have low quality scores are costing you more per click than they should.")

# KPI cards
total_kw       = len(df_kw)
high_risk      = len(df_kw[df_kw["stupidity_tax_flag"] == "HIGH RISK — Low quality score"])
no_data        = len(df_kw[df_kw["stupidity_tax_flag"] == "NO DATA — Never served"])
good_kw        = len(df_kw[df_kw["stupidity_tax_flag"] == "GOOD — Keep running"])
avg_qs         = df_kw[df_kw["quality_score"] > 0]["quality_score"].mean()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Keywords",   f"{total_kw:,}")
k2.metric("High Risk",        f"{high_risk}", delta=f"{high_risk} need attention", delta_color="inverse")
k3.metric("No Data / Unserved", f"{no_data}")
k4.metric("Good Keywords",    f"{good_kw}")
k5.metric("Avg Quality Score", f"{avg_qs:.1f}/10" if avg_qs > 0 else "N/A")

col1, col2 = st.columns(2)

with col1:
    flag_counts = df_kw["stupidity_tax_flag"].value_counts().reset_index()
    flag_counts.columns = ["flag", "count"]
    color_map = {
        "HIGH RISK — Low quality score": "#E24B4A",
        "NO DATA — Never served":        "#EF9F27",
        "AVERAGE — Room to improve":     "#378ADD",
        "GOOD — Keep running":           "#1D9E75",
        "PAUSED / NEGATIVE":             "#888780"
    }
    fig1 = px.bar(flag_counts, x="count", y="flag", orientation="h",
                  title="Keywords by health status",
                  color="flag", color_discrete_map=color_map)
    fig1.update_layout(showlegend=False, height=320, margin=dict(t=40,b=20),
                       yaxis_title="", xaxis_title="Count")
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    qs_dist = df_kw[df_kw["quality_score"] > 0]["quality_score"].value_counts().sort_index().reset_index()
    qs_dist.columns = ["quality_score", "count"]
    fig2 = px.bar(qs_dist, x="quality_score", y="count",
                  title="Quality score distribution (0 = no data excluded)",
                  color="quality_score",
                  color_continuous_scale=["#E24B4A","#EF9F27","#1D9E75"])
    fig2.update_layout(height=320, margin=dict(t=40,b=20),
                       xaxis_title="Quality Score (1-10)", yaxis_title="Count",
                       showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

# High risk keyword table
st.markdown("### High risk keywords — fix or pause these")
risk_df = df_kw[df_kw["stupidity_tax_flag"].isin([
    "HIGH RISK — Low quality score", "AVERAGE — Room to improve"
])][["keyword","match_type","quality_score","creative_quality",
     "landing_page_quality","predicted_ctr","campaign_name","stupidity_tax_flag"
]].sort_values("quality_score")

st.dataframe(
    risk_df.rename(columns={
        "keyword":             "Keyword",
        "match_type":          "Match Type",
        "quality_score":       "Quality Score",
        "creative_quality":    "Ad Quality",
        "landing_page_quality":"Landing Page",
        "predicted_ctr":       "Predicted CTR",
        "campaign_name":       "Campaign",
        "stupidity_tax_flag":  "Status"
    }),
    use_container_width=True, hide_index=True
)

st.divider()

# ─────────────────────────────────────────────
# SECTION 2: AD INTELLIGENCE
# ─────────────────────────────────────────────
st.markdown("## 📢 Ad Intelligence — Health & Strength")
st.caption("Ad strength tells Google how well your ad is likely to perform. AVERAGE or POOR ads waste spend.")

a1, a2, a3, a4 = st.columns(4)
total_ads    = len(df_ad)
enabled_ads  = len(df_ad[df_ad["ad_status"] == "ENABLED"])
good_ads     = len(df_ad[df_ad["health_flag"].isin(["EXCELLENT","GOOD"])])
needs_work   = len(df_ad[df_ad["health_flag"] == "NEEDS WORK"])

a1.metric("Total Ads",      f"{total_ads}")
a2.metric("Active (Enabled)", f"{enabled_ads}")
a3.metric("Good / Excellent", f"{good_ads}")
a4.metric("Needs Work",     f"{needs_work}", delta=f"{needs_work} to improve", delta_color="inverse")

col3, col4 = st.columns(2)

with col3:
    strength_counts = df_ad["ad_strength"].value_counts().reset_index()
    strength_counts.columns = ["strength", "count"]
    strength_color = {
        "EXCELLENT": "#1D9E75",
        "GOOD":      "#639922",
        "AVERAGE":   "#EF9F27",
        "POOR":      "#E24B4A",
        "PENDING":   "#888780"
    }
    fig3 = px.pie(strength_counts, names="strength", values="count",
                  title="Ad strength breakdown",
                  color="strength", color_discrete_map=strength_color)
    fig3.update_layout(height=320, margin=dict(t=40,b=20))
    st.plotly_chart(fig3, use_container_width=True)

with col4:
    status_camp = df_ad.groupby(["campaign_name","ad_status"]).size().reset_index(name="count")
    # shorten long campaign names
    status_camp["campaign_name"] = status_camp["campaign_name"].str[:30]
    fig4 = px.bar(status_camp, x="count", y="campaign_name", color="ad_status",
                  orientation="h", title="Ads per campaign (enabled vs paused)",
                  color_discrete_map={"ENABLED":"#1D9E75","PAUSED":"#888780"})
    fig4.update_layout(height=320, margin=dict(t=40,b=20),
                       yaxis_title="", xaxis_title="Ad count")
    st.plotly_chart(fig4, use_container_width=True)

# Ad detail table — only enabled ads
st.markdown("### Active ads detail")
active_ads = df_ad[df_ad["ad_status"] == "ENABLED"][[
    "campaign_name","headline_1","headline_2","description_1",
    "ad_strength","total_headlines","total_descriptions","landing_page_url","health_flag"
]].rename(columns={
    "campaign_name":    "Campaign",
    "headline_1":       "Headline 1",
    "headline_2":       "Headline 2",
    "description_1":    "Description",
    "ad_strength":      "Strength",
    "total_headlines":  "# Headlines",
    "total_descriptions":"# Descriptions",
    "landing_page_url": "Landing Page",
    "health_flag":      "Health"
})
st.dataframe(active_ads, use_container_width=True, hide_index=True)

st.divider()

# ─────────────────────────────────────────────
# SECTION 3: HOURLY INTELLIGENCE
# ─────────────────────────────────────────────
st.markdown("## ⏰ Hourly Intelligence — When do people engage?")
st.caption("Use this to set ad scheduling — run ads harder during peak hours, pull back during dead hours.")

col5, col6 = st.columns(2)

with col5:
    # Clicks by hour of day
    hourly_clicks = df_hour.groupby("hour").agg(
        clicks=("clicks","sum"),
        impressions=("impressions","sum"),
        conversions=("conversions","sum")
    ).reset_index().sort_values("hour")

    fig5 = px.bar(hourly_clicks, x="hour", y="clicks",
                  title="Clicks by hour of day",
                  color="clicks", color_continuous_scale=["#B5D4F4","#0C447C"])
    fig5.update_layout(height=320, margin=dict(t=40,b=20),
                       xaxis_title="Hour (24h)", yaxis_title="Clicks",
                       showlegend=False)
    fig5.update_xaxes(tickmode="linear", dtick=1)
    st.plotly_chart(fig5, use_container_width=True)

with col6:
    # Conversions by hour
    conv_hour = df_hour[df_hour["conversions"] > 0].groupby("hour").agg(
        conversions=("conversions","sum"),
        cost_usd=("cost_usd","sum")
    ).reset_index()

    if len(conv_hour) > 0:
        fig6 = px.bar(conv_hour, x="hour", y="conversions",
                      title="Conversions by hour of day",
                      color="conversions", color_continuous_scale=["#9FE1CB","#085041"],
                      text="conversions")
        fig6.update_traces(textposition="outside")
        fig6.update_layout(height=320, margin=dict(t=40,b=20),
                           xaxis_title="Hour (24h)", yaxis_title="Conversions",
                           showlegend=False)
        fig6.update_xaxes(tickmode="linear", dtick=1)
        st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("No conversion data by hour yet — will populate as more data flows in.")

# Heatmap: day of week x hour
st.markdown("### Impression heatmap — day of week vs hour")
heatmap_data = df_hour.groupby(["day_of_week","hour"]).agg(
    impressions=("impressions","sum")
).reset_index()

pivot = heatmap_data.pivot(index="day_of_week", columns="hour", values="impressions").fillna(0)
dow_order = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]
pivot = pivot.reindex([d for d in dow_order if d in pivot.index])

fig7 = px.imshow(pivot, color_continuous_scale="Blues",
                 labels=dict(x="Hour of Day", y="Day of Week", color="Impressions"),
                 title="When does your ad show? (impressions by hour + day)",
                 aspect="auto")
fig7.update_layout(height=350, margin=dict(t=50,b=20))
st.plotly_chart(fig7, use_container_width=True)

# Time of day summary
st.markdown("### Best time windows to run ads")
time_summary = df_hour.groupby("time_of_day_label").agg(
    clicks=("clicks","sum"),
    impressions=("impressions","sum"),
    conversions=("conversions","sum"),
    cost_usd=("cost_usd","sum")
).reset_index().sort_values("clicks", ascending=False)
time_summary["ctr_pct"] = (time_summary["clicks"] / time_summary["impressions"] * 100).round(1)

st.dataframe(
    time_summary.rename(columns={
        "time_of_day_label": "Time Window",
        "clicks":            "Clicks",
        "impressions":       "Impressions",
        "conversions":       "Conversions",
        "cost_usd":          "Spend ($)",
        "ctr_pct":           "CTR %"
    }),
    use_container_width=True, hide_index=True
)