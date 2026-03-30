import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import get_client, render_sidebar

# --- PAGE SETUP ---
st.set_page_config(page_title="Google Ads Intelligence", page_icon="🧠", layout="wide")
render_sidebar()
client = get_client()

st.title("🧠 Google Ads Deep Intelligence")
st.caption("Built directly from raw BigQuery tables · No views · No duplicates")

# ─────────────────────────────────────────────
# DATA LOADERS
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_keywords():
    return client.query("""
        WITH deduped AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        ad_group_criterion_keyword_text,
                        ad_group_criterion_keyword_match_type,
                        ad_group_id,
                        campaign_id
                    ORDER BY _PARTITIONTIME DESC
                ) AS rn
            FROM `the-brain-487614.Google_ads.p_ads_Keyword_9403250839`
            WHERE ad_group_criterion_negative IS NOT TRUE
        )
        SELECT
            k.ad_group_criterion_keyword_text                              AS keyword,
            k.ad_group_criterion_keyword_match_type                        AS match_type,
            k.ad_group_criterion_status                                    AS keyword_status,
            CAST(k.ad_group_criterion_quality_info_quality_score AS INT64) AS quality_score,
            k.ad_group_criterion_quality_info_creative_quality_score       AS creative_quality,
            k.ad_group_criterion_quality_info_post_click_quality_score     AS landing_page_quality,
            k.ad_group_criterion_quality_info_search_predicted_ctr         AS predicted_ctr,
            ROUND(CAST(k.ad_group_criterion_position_estimates_first_page_cpc_micros AS INT64) / 1000000.0, 2) AS first_page_cpc_usd,
            c.campaign_name,
            c.campaign_status,
            CASE
                WHEN k.ad_group_criterion_status = 'ENABLED'
                 AND CAST(k.ad_group_criterion_quality_info_quality_score AS INT64) BETWEEN 1 AND 4
                THEN 'HIGH RISK — Low quality score'
                WHEN k.ad_group_criterion_status = 'ENABLED'
                 AND CAST(k.ad_group_criterion_quality_info_quality_score AS INT64) = 0
                 AND k.ad_group_criterion_quality_info_creative_quality_score = 'UNSPECIFIED'
                THEN 'NO DATA — Never served'
                WHEN k.ad_group_criterion_status = 'ENABLED'
                 AND CAST(k.ad_group_criterion_quality_info_quality_score AS INT64) BETWEEN 5 AND 6
                THEN 'AVERAGE — Room to improve'
                WHEN k.ad_group_criterion_status = 'ENABLED'
                 AND CAST(k.ad_group_criterion_quality_info_quality_score AS INT64) >= 7
                THEN 'GOOD — Keep running'
                ELSE 'PAUSED / NEGATIVE'
            END AS health_flag
        FROM deduped k
        LEFT JOIN (
            SELECT DISTINCT campaign_id, campaign_name, campaign_status
            FROM `the-brain-487614.Google_ads.p_ads_Campaign_9403250839`
        ) c USING (campaign_id)
        WHERE k.rn = 1
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_ads():
    return client.query("""
        SELECT DISTINCT
            a.ad_group_ad_ad_id                              AS ad_id,
            a.campaign_id,
            c.campaign_name,
            c.campaign_status,
            a.ad_group_ad_status                             AS ad_status,
            a.ad_group_ad_ad_strength                        AS ad_strength,
            a.ad_group_ad_ad_type                            AS ad_type,
            a.ad_group_ad_policy_summary_approval_status     AS approval_status,
            JSON_VALUE(
                JSON_QUERY_ARRAY(a.ad_group_ad_ad_final_urls)[OFFSET(0)]
            )                                                AS landing_page_url,
            CASE
                WHEN a.ad_group_ad_policy_summary_approval_status = 'DISAPPROVED'
                THEN '🚨 DISAPPROVED'
                WHEN a.ad_group_ad_ad_strength IN ('EXCELLENT', 'GOOD')
                 AND a.ad_group_ad_policy_summary_approval_status = 'APPROVED'
                THEN '✅ Healthy'
                WHEN a.ad_group_ad_ad_strength = 'AVERAGE'
                THEN '⚠️ Average'
                WHEN a.ad_group_ad_ad_strength = 'POOR'
                THEN '🔴 Poor'
                WHEN a.ad_group_ad_ad_strength = 'PENDING'
                THEN '⏳ Pending'
                ELSE '⚠️ Check'
            END AS health_flag
        FROM `the-brain-487614.Google_ads.p_ads_Ad_9403250839` a
        LEFT JOIN (
            SELECT DISTINCT campaign_id, campaign_name, campaign_status
            FROM `the-brain-487614.Google_ads.p_ads_Campaign_9403250839`
        ) c USING (campaign_id)
        WHERE a.ad_group_ad_ad_type = 'RESPONSIVE_SEARCH_AD'
        ORDER BY a.ad_group_ad_status, a.ad_group_ad_ad_strength
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_hourly():
    return client.query("""
        SELECT
            CAST(segments_hour AS INT64)                      AS hour,
            segments_day_of_week                              AS day_of_week,
            segments_date                                     AS date,
            segments_device                                   AS device,
            SUM(CAST(metrics_clicks AS INT64))                AS clicks,
            SUM(CAST(metrics_impressions AS INT64))           AS impressions,
            SUM(CAST(metrics_conversions AS FLOAT64))         AS conversions,
            SUM(CAST(metrics_cost_micros AS INT64)) / 1000000.0 AS cost_usd
        FROM `the-brain-487614.Google_ads.p_ads_HourlyCampaignStats_9403250839`
        GROUP BY hour, day_of_week, date, device
        ORDER BY date DESC, hour
    """).to_dataframe()

df_kw    = load_keywords()
df_ad    = load_ads()
df_hour  = load_hourly()

# ─────────────────────────────────────────────
# SECTION 1 — KEYWORD HEALTH
# ─────────────────────────────────────────────
st.markdown("## 🔑 Keyword Health")
st.caption("Historical quality scores from paused campaigns — review before reactivating.")

total_kw   = len(df_kw)
high_risk  = len(df_kw[df_kw["health_flag"] == "HIGH RISK — Low quality score"])
no_data    = len(df_kw[df_kw["health_flag"] == "NO DATA — Never served"])
good_kw    = len(df_kw[df_kw["health_flag"] == "GOOD — Keep running"])
avg_qs     = df_kw[df_kw["quality_score"] > 0]["quality_score"].mean()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Keywords",     f"{total_kw:,}")
k2.metric("🚨 High Risk",       f"{high_risk}", delta=f"{high_risk} need fixing", delta_color="inverse")
k3.metric("⚪ Never Served",    f"{no_data}")
k4.metric("✅ Good Keywords",   f"{good_kw}")
k5.metric("Avg Quality Score",  f"{avg_qs:.1f}/10" if avg_qs > 0 else "N/A")

col1, col2 = st.columns(2)
with col1:
    color_map = {
        "HIGH RISK — Low quality score": "#E24B4A",
        "NO DATA — Never served":        "#EF9F27",
        "AVERAGE — Room to improve":     "#378ADD",
        "GOOD — Keep running":           "#1D9E75",
        "PAUSED / NEGATIVE":             "#888780"
    }
    flag_counts = df_kw["health_flag"].value_counts().reset_index()
    flag_counts.columns = ["flag", "count"]
    fig1 = px.bar(flag_counts, x="count", y="flag", orientation="h",
                  title="Keywords by health status",
                  color="flag", color_discrete_map=color_map)
    fig1.update_layout(showlegend=False, height=300,
                       plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                       yaxis_title="", xaxis_title="Count")
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    qs_dist = df_kw[df_kw["quality_score"] > 0]["quality_score"].value_counts().sort_index().reset_index()
    qs_dist.columns = ["quality_score", "count"]
    if len(qs_dist) > 0:
        fig2 = px.bar(qs_dist, x="quality_score", y="count",
                      title="Quality score distribution (scored keywords only)",
                      color="quality_score",
                      color_continuous_scale=["#E24B4A", "#EF9F27", "#1D9E75"])
        fig2.update_layout(height=300, showlegend=False,
                           plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                           xaxis_title="Quality Score (1-10)", yaxis_title="Count")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No scored keywords yet.")

# Keywords with real scores
scored = df_kw[df_kw["quality_score"] > 0].sort_values("quality_score")
if len(scored) > 0:
    st.markdown("### 📊 Keywords with quality scores")
    st.dataframe(
        scored[["keyword","match_type","quality_score","creative_quality",
                "landing_page_quality","predicted_ctr","campaign_name","health_flag"]]
        .rename(columns={
            "keyword":          "Keyword",
            "match_type":       "Match Type",
            "quality_score":    "Quality Score",
            "creative_quality": "Ad Quality",
            "landing_page_quality": "Landing Page",
            "predicted_ctr":    "Predicted CTR",
            "campaign_name":    "Campaign",
            "health_flag":      "Status"
        }),
        use_container_width=True, hide_index=True
    )

# Never served keywords
never_served = df_kw[df_kw["health_flag"] == "NO DATA — Never served"]
with st.expander(f"⚪ Never served keywords ({len(never_served)}) — review before reactivating"):
    st.dataframe(
        never_served[["keyword","match_type","campaign_name","keyword_status","first_page_cpc_usd"]]
        .rename(columns={
            "keyword":           "Keyword",
            "match_type":        "Match Type",
            "campaign_name":     "Campaign",
            "keyword_status":    "Status",
            "first_page_cpc_usd":"Est. First Page CPC ($)"
        }),
        use_container_width=True, hide_index=True
    )

st.divider()

# ─────────────────────────────────────────────
# SECTION 2 — AD HEALTH
# ─────────────────────────────────────────────
st.markdown("## 📢 Ad Health")
st.caption("Ad strength and approval status across all campaigns.")

total_ads    = len(df_ad)
enabled_ads  = len(df_ad[df_ad["ad_status"] == "ENABLED"])
disapproved  = len(df_ad[df_ad["approval_status"] == "DISAPPROVED"])
good_ads     = len(df_ad[df_ad["ad_strength"].isin(["EXCELLENT","GOOD"])])

a1, a2, a3, a4 = st.columns(4)
a1.metric("Total Ads",          f"{total_ads}")
a2.metric("Active (Enabled)",   f"{enabled_ads}")
a3.metric("✅ Good / Excellent", f"{good_ads}")
a4.metric("🚨 Disapproved",     f"{disapproved}",
          delta=f"{disapproved} not showing", delta_color="inverse")

col3, col4 = st.columns(2)
with col3:
    strength_counts = df_ad["ad_strength"].value_counts().reset_index()
    strength_counts.columns = ["strength", "count"]
    fig3 = px.pie(strength_counts, names="strength", values="count",
                  title="Ad strength breakdown",
                  color="strength", color_discrete_map={
                      "EXCELLENT": "#1D9E75", "GOOD":    "#639922",
                      "AVERAGE":   "#EF9F27", "POOR":    "#E24B4A",
                      "PENDING":   "#888780"
                  })
    fig3.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig3, use_container_width=True)

with col4:
    approval_counts = df_ad["approval_status"].value_counts().reset_index()
    approval_counts.columns = ["status", "count"]
    fig4 = px.bar(approval_counts, x="count", y="status", orientation="h",
                  title="Approval status breakdown",
                  color="status", color_discrete_map={
                      "APPROVED":          "#1D9E75",
                      "DISAPPROVED":       "#E24B4A",
                      "APPROVED_LIMITED":  "#EF9F27",
                      "UNKNOWN":           "#888780"
                  })
    fig4.update_layout(height=300, showlegend=False,
                       plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                       yaxis_title="", xaxis_title="Count")
    st.plotly_chart(fig4, use_container_width=True)

# Disapproved ads — highlighted
if disapproved > 0:
    st.markdown("### 🚨 Disapproved ads — these are NOT showing")
    st.dataframe(
        df_ad[df_ad["approval_status"] == "DISAPPROVED"][[
            "campaign_name","ad_status","ad_strength","landing_page_url","health_flag"
        ]].rename(columns={
            "campaign_name":  "Campaign",
            "ad_status":      "Status",
            "ad_strength":    "Strength",
            "landing_page_url":"Landing Page",
            "health_flag":    "Health"
        }),
        use_container_width=True, hide_index=True
    )

st.markdown("### All active ads")
st.dataframe(
    df_ad[df_ad["ad_status"] == "ENABLED"][[
        "campaign_name","campaign_status","ad_strength",
        "approval_status","landing_page_url","health_flag"
    ]].rename(columns={
        "campaign_name":   "Campaign",
        "campaign_status": "Campaign Status",
        "ad_strength":     "Strength",
        "approval_status": "Approval",
        "landing_page_url":"Landing Page",
        "health_flag":     "Health"
    }),
    use_container_width=True, hide_index=True
)

st.divider()

# ─────────────────────────────────────────────
# SECTION 3 — HOURLY INTELLIGENCE
# ─────────────────────────────────────────────
st.markdown("## ⏰ Hourly Intelligence")
st.caption("When do people click and convert? Use this to set ad scheduling.")

col5, col6 = st.columns(2)

hourly_agg = df_hour.groupby("hour").agg(
    clicks=("clicks","sum"),
    impressions=("impressions","sum"),
    conversions=("conversions","sum")
).reset_index().sort_values("hour")

with col5:
    fig5 = px.bar(hourly_agg, x="hour", y="clicks",
                  title="Clicks by hour of day",
                  color="clicks", color_continuous_scale=["#B5D4F4","#0C447C"])
    fig5.update_layout(height=300, showlegend=False,
                       xaxis_title="Hour (24h)", yaxis_title="Clicks",
                       plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    fig5.update_xaxes(tickmode="linear", dtick=1)
    st.plotly_chart(fig5, use_container_width=True)

with col6:
    conv_hour = hourly_agg[hourly_agg["conversions"] > 0]
    if len(conv_hour) > 0:
        fig6 = px.bar(conv_hour, x="hour", y="conversions",
                      title="Conversions by hour of day",
                      color="conversions",
                      color_continuous_scale=["#9FE1CB","#085041"],
                      text="conversions")
        fig6.update_traces(textposition="outside")
        fig6.update_layout(height=300, showlegend=False,
                           xaxis_title="Hour (24h)", yaxis_title="Conversions",
                           plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        fig6.update_xaxes(tickmode="linear", dtick=1)
        st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("No conversion data by hour yet.")

# Heatmap
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
fig7.update_layout(height=350, paper_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig7, use_container_width=True)

# Best time windows
st.markdown("### Best time windows to run ads")
time_windows = df_hour.copy()
time_windows["time_label"] = pd.cut(
    time_windows["hour"],
    bins=[-1, 5, 11, 16, 20, 23],
    labels=["Night (12am–6am)", "Morning (6am–12pm)",
            "Afternoon (12pm–5pm)", "Evening (5pm–9pm)", "Late Night (9pm–12am)"]
)
time_summary = time_windows.groupby("time_label", observed=True).agg(
    clicks=("clicks","sum"),
    impressions=("impressions","sum"),
    conversions=("conversions","sum")
).reset_index().sort_values("clicks", ascending=False)
time_summary["ctr_pct"] = (
    time_summary["clicks"] / time_summary["impressions"].replace(0, 1) * 100
).round(1)
st.dataframe(
    time_summary.rename(columns={
        "time_label":  "Time Window",
        "clicks":      "Clicks",
        "impressions": "Impressions",
        "conversions": "Conversions",
        "ctr_pct":     "CTR %"
    }),
    use_container_width=True, hide_index=True
)