import streamlit as st
import pandas as pd
from utils import get_client, render_sidebar

st.set_page_config(
    page_title="The Brain — Premier Energy",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

client = get_client()

# --- CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { background: #1a1f2e; }
section[data-testid="stSidebar"] * { color: #c8cdd8 !important; }
h1 { color: #fff !important; font-weight: 700 !important;
     border-bottom: 3px solid rgba(255,255,255,0.2);
     padding-bottom: 0.5rem !important; margin-bottom: 0.25rem !important; }
.section-label {
    color: rgba(255,255,255,0.38); font-size: 0.72rem; font-weight: 600;
    letter-spacing: 0.1em; text-transform: uppercase;
    margin: 2rem 0 0.75rem; padding-bottom: 0.4rem;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}
.nav-card {
    background: #1e2436; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px; padding: 22px 20px;
}
.nav-card .icon { font-size: 26px; margin-bottom: 10px; }
.nav-card h3 { color: #fff; font-size: 0.95rem; font-weight: 600; margin: 0 0 6px; }
.nav-card p  { color: rgba(255,255,255,0.5); font-size: 0.8rem; margin: 0; line-height: 1.5; }
.nav-card .tag {
    display: inline-block; margin-top: 12px;
    background: rgba(55,138,221,0.15); color: #7ab8f5;
    font-size: 0.7rem; font-weight: 600; letter-spacing: 0.04em;
    padding: 3px 10px; border-radius: 20px;
}
.kpi-box {
    background: #1e2436; border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px; padding: 18px 14px; text-align: center;
}
.kpi-box .val { font-size: 1.5rem; font-weight: 700; color: #fff; }
.kpi-box .lbl { font-size: 0.72rem; color: rgba(255,255,255,0.42); margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
render_sidebar()

# --- HEADER ---
st.title("⚡ The Brain")
st.caption("Premier Energy Solutions — Business Intelligence Dashboard")
st.markdown("")

# --- LIVE KPI SNAPSHOT ---
@st.cache_data(ttl=3600)
def load_snapshot():
    try:
        return client.query("""
            WITH rev AS (
                SELECT
                    SUM(ii.total)                                   AS revenue,
                    SUM(ii.total - COALESCE(ii.total_cost, 0))      AS gp_no_labor
                FROM `the-brain-487614.servicetitan.invoice` i
                JOIN `the-brain-487614.servicetitan.invoice_item` ii ON i.id = ii.invoice_id
                JOIN `the-brain-487614.servicetitan.job` j ON i.job_id = j.id
                WHERE i._fivetran_deleted = FALSE AND i.active = TRUE
                  AND ii._fivetran_deleted = FALSE AND ii.active = TRUE
                  AND j.job_status = 'Completed'
                  AND DATE(j.completed_on) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
            ),
            jobs AS (
                SELECT COUNT(*) AS total_jobs
                FROM `the-brain-487614.servicetitan.job`
                WHERE _fivetran_deleted = FALSE AND job_status = 'Completed'
                  AND DATE(completed_on) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
            ),
            calls AS (
                SELECT
                    COUNTIF(lead_call_call_type = 'Booked')                       AS booked,
                    COUNTIF(lead_call_call_type IN ('Booked','Unbooked'))          AS bookable
                FROM `the-brain-487614.servicetitan.call`
                WHERE _fivetran_deleted = FALSE
                  AND lead_call_direction = 'Inbound'
                  AND DATE(lead_call_created_on) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
            ),
            cancels AS (
                SELECT
                    COUNTIF(job_status = 'Canceled') AS cancelled,
                    COUNT(*)                          AS total
                FROM `the-brain-487614.servicetitan.job`
                WHERE _fivetran_deleted = FALSE
                  AND DATE(created_on) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
            )
            SELECT
                rev.revenue,
                ROUND(rev.gp_no_labor / NULLIF(rev.revenue,0) * 100, 1) AS gp_margin_pct,
                jobs.total_jobs,
                ROUND(calls.booked / NULLIF(calls.bookable,0) * 100, 1)  AS booking_rate_pct,
                ROUND(cancels.cancelled / NULLIF(cancels.total,0) * 100, 1) AS cancel_rate_pct
            FROM rev, jobs, calls, cancels
        """).to_dataframe().iloc[0]
    except Exception:
        return None

snap = load_snapshot()

st.markdown('<p class="section-label">This month at a glance</p>', unsafe_allow_html=True)
cols = st.columns(5)
kpis = [
    (f"${snap['revenue']:,.0f}"    if snap is not None and snap['revenue']         else "—", "Revenue MTD"),
    (f"{snap['gp_margin_pct']}%"   if snap is not None and snap['gp_margin_pct']   else "—", "GP Margin"),
    (f"{int(snap['total_jobs'])}"  if snap is not None                             else "—", "Jobs Completed"),
    (f"{snap['booking_rate_pct']}%" if snap is not None and snap['booking_rate_pct'] else "—", "Booking Rate"),
    (f"{snap['cancel_rate_pct']}%"  if snap is not None and snap['cancel_rate_pct']  else "—", "Cancel Rate"),
]
for col, (val, lbl) in zip(cols, kpis):
    col.markdown(
        f'<div class="kpi-box"><div class="val">{val}</div><div class="lbl">{lbl}</div></div>',
        unsafe_allow_html=True
    )

st.markdown("")

# --- NAV CARDS ---
st.markdown('<p class="section-label">Financial performance</p>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.markdown('<div class="nav-card"><div class="icon">💰</div><h3>Gross Profit & KPIs</h3><p>Revenue, material cost, labor cost, GP margin, and weekly trends by department and technician.</p><span class="tag">GP · Technicians · Calls</span></div>', unsafe_allow_html=True)
    st.page_link("pages/6_Profit.py", label="→ Open Gross Profit & KPIs")

with c2:
    st.markdown('<div class="nav-card"><div class="icon">❌</div><h3>Cancellation Analysis</h3><p>Which job types cancel most, when it happens, cancellation reasons, and overbooking multipliers.</p><span class="tag">Scheduling · Risk · Overbooking</span></div>', unsafe_allow_html=True)
    st.page_link("pages/3_Cancellation_Analysis.py", label="→ Open Cancellation Analysis")

st.markdown('<p class="section-label">Google Ads</p>', unsafe_allow_html=True)
c3, c4, c5 = st.columns(3)
with c3:
    st.markdown('<div class="nav-card"><div class="icon">📊</div><h3>Ads Performance</h3><p>Daily spend vs clicks, device breakdown, conversions, and CTR by day of week.</p><span class="tag">Spend · CTR · Conversions</span></div>', unsafe_allow_html=True)
    st.page_link("pages/4_Google_Ads.py", label="→ Open Ads Performance")

with c4:
    st.markdown('<div class="nav-card"><div class="icon">🧠</div><h3>Ads Intelligence</h3><p>Keyword quality scores, the stupidity tax, ad strength health, and hourly engagement heatmaps.</p><span class="tag">Quality · Keywords · Hourly</span></div>', unsafe_allow_html=True)
    st.page_link("pages/5_Google_Ads_Intelligence.py", label="→ Open Ads Intelligence")

with c5:
    st.markdown('<div class="nav-card"><div class="icon">🔍</div><h3>Ads Data Explorer</h3><p>Browse all 34 raw Google Ads BigQuery tables — structure, schema, and live row data.</p><span class="tag">Raw data · Schema · GCLID</span></div>', unsafe_allow_html=True)
    st.page_link("pages/7_Google_Ads_explorer.py", label="→ Open Ads Explorer")

st.markdown('<p class="section-label">Calls & data</p>', unsafe_allow_html=True)
c6, c7, c8 = st.columns(3)
with c6:
    st.markdown('<div class="nav-card"><div class="icon">📞</div><h3>CallRail</h3><p>Call volume trends, channel performance, hourly heatmaps, geographic breakdown, and tracker health.</p><span class="tag">Calls · Channels · GCLID</span></div>', unsafe_allow_html=True)
    st.page_link("pages/8_CallRail.py", label="→ Open CallRail")

with c7:
    st.markdown('<div class="nav-card"><div class="icon">🗄️</div><h3>ServiceTitan Explorer</h3><p>Browse all 59 ServiceTitan tables — customers, jobs, invoices, technicians, memberships, and more.</p><span class="tag">40k customers · 22k jobs</span></div>', unsafe_allow_html=True)
    st.page_link("pages/2_ServiceTitan_Explorer.py", label="→ Open Data Explorer")

with c8:
    st.markdown('<div class="nav-card" style="opacity:0.4;cursor:default;"><div class="icon">🔮</div><h3>More coming soon</h3><p>Membership forecasting, technician scorecards, and campaign ROI attribution.</p><span class="tag" style="background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.35);">Roadmap</span></div>', unsafe_allow_html=True)

st.markdown("")
st.markdown("---")
st.caption("Data sourced from BigQuery · the-brain-487614 · Refreshes every hour")