import streamlit as st
import pandas as pd
import plotly.express as px
from utils import get_client, render_sidebar

# --- PAGE SETUP ---
st.set_page_config(page_title="Cancellation Analysis", page_icon="❌", layout="wide")

# --- SIDEBAR (always first) ---
render_sidebar()

# --- ADD PAGE-SPECIFIC SIDEBAR FILTERS AFTER NAV ---
st.sidebar.markdown("---")
st.sidebar.header("🔍 Filters")

# --- CLIENT ---
client = get_client()

# --- TITLE ---
st.title("❌ Job Cancellation Analysis")
st.markdown("Understanding which jobs cancel, when, and why — to enable smarter scheduling.")

# --- LOAD DATA ---
@st.cache_data(ttl=3600)
def load_cancellation_data():
    return client.query("""
        SELECT
            jt.name                                         AS job_type,
            bu.name                                         AS business_unit,
            COUNT(*)                                        AS total_jobs,
            COUNTIF(j.job_status = 'Canceled')              AS cancelled_jobs,
            ROUND(
                COUNTIF(j.job_status = 'Canceled') * 100.0 / COUNT(*), 2
            )                                               AS cancellation_rate_pct,
            ROUND(AVG(
                CASE WHEN j.job_status = 'Canceled'
                THEN TIMESTAMP_DIFF(jcl.created_on, j.created_on, HOUR)
                END
            ), 1)                                           AS avg_hours_to_cancellation,
            ROUND(AVG(
                CASE WHEN j.job_status = 'Canceled'
                THEN TIMESTAMP_DIFF(jcl.created_on, j.created_on, HOUR) / 24.0
                END
            ), 1)                                           AS avg_days_to_cancellation
        FROM `the-brain-487614.servicetitan.job` j
        JOIN `the-brain-487614.servicetitan.job_type` jt ON j.job_type_id = jt.id
        JOIN `the-brain-487614.servicetitan.business_unit` bu ON j.business_unit_id = bu.id
        LEFT JOIN `the-brain-487614.servicetitan.job_canceled_log` jcl ON jcl.job_id = j.id
        WHERE j._fivetran_deleted = FALSE
            AND j.created_on > '2020-01-01'
            AND jt.name NOT LIKE '%Imported%'
        GROUP BY 1, 2
        HAVING COUNT(*) >= 10
        ORDER BY cancellation_rate_pct DESC
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_cancellation_reasons():
    return client.query("""
        SELECT
            r.name      AS cancel_reason,
            bu.name     AS business_unit,
            COUNT(*)    AS total_cancellations,
            jcl.memo
        FROM `the-brain-487614.servicetitan.job_canceled_log` jcl
        JOIN `the-brain-487614.servicetitan.job_cancel_reason` r ON jcl.reason_id = r.id
        JOIN `the-brain-487614.servicetitan.job` j ON jcl.job_id = j.id
        JOIN `the-brain-487614.servicetitan.business_unit` bu ON j.business_unit_id = bu.id
        WHERE jcl._fivetran_deleted = FALSE
            AND j._fivetran_deleted = FALSE
        GROUP BY 1, 2, jcl.memo
        ORDER BY total_cancellations DESC
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_cancellation_by_month():
    return client.query("""
        SELECT
            FORMAT_DATE('%Y-%m', DATE(j.created_on))    AS month,
            bu.name                                      AS business_unit,
            COUNT(*)                                     AS total_jobs,
            COUNTIF(j.job_status = 'Canceled')           AS cancelled_jobs,
            ROUND(
                COUNTIF(j.job_status = 'Canceled') * 100.0 / COUNT(*), 2
            )                                            AS cancellation_rate_pct
        FROM `the-brain-487614.servicetitan.job` j
        JOIN `the-brain-487614.servicetitan.business_unit` bu ON j.business_unit_id = bu.id
        WHERE j._fivetran_deleted = FALSE
            AND j.created_on > '2020-01-01'
        GROUP BY 1, 2
        ORDER BY 1
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_cancellation_by_dayofweek():
    return client.query("""
        SELECT
            FORMAT_DATE('%A', DATE(j.created_on))        AS day_of_week,
            EXTRACT(DAYOFWEEK FROM j.created_on)         AS day_num,
            COUNT(*)                                     AS total_jobs,
            COUNTIF(j.job_status = 'Canceled')           AS cancelled_jobs,
            ROUND(
                COUNTIF(j.job_status = 'Canceled') * 100.0 / COUNT(*), 2
            )                                            AS cancellation_rate_pct
        FROM `the-brain-487614.servicetitan.job` j
        WHERE j._fivetran_deleted = FALSE
            AND j.created_on > '2020-01-01'
        GROUP BY 1, 2
        ORDER BY 2
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_recent_cancellations():
    return client.query("""
        SELECT
            j.job_number,
            c.name                                              AS customer,
            jt.name                                             AS job_type,
            bu.name                                             AS business_unit,
            DATE(j.created_on)                                  AS job_created,
            DATE(jcl.created_on)                                AS cancelled_on,
            TIMESTAMP_DIFF(jcl.created_on, j.created_on, HOUR) AS hours_to_cancel,
            r.name                                              AS cancel_reason,
            jcl.memo                                            AS notes
        FROM `the-brain-487614.servicetitan.job_canceled_log` jcl
        JOIN `the-brain-487614.servicetitan.job` j ON jcl.job_id = j.id
        JOIN `the-brain-487614.servicetitan.customer` c ON j.customer_id = c.id
        JOIN `the-brain-487614.servicetitan.job_type` jt ON j.job_type_id = jt.id
        JOIN `the-brain-487614.servicetitan.business_unit` bu ON j.business_unit_id = bu.id
        LEFT JOIN `the-brain-487614.servicetitan.job_cancel_reason` r ON jcl.reason_id = r.id
        WHERE jcl._fivetran_deleted = FALSE
            AND j._fivetran_deleted = FALSE
        ORDER BY jcl.created_on DESC
        LIMIT 100
    """).to_dataframe()

# --- LOAD ALL DATA ---
with st.spinner("Loading cancellation data..."):
    df         = load_cancellation_data()
    df_reasons = load_cancellation_reasons()
    df_monthly = load_cancellation_by_month()
    df_dow     = load_cancellation_by_dayofweek()
    df_recent  = load_recent_cancellations()

# --- PAGE-SPECIFIC SIDEBAR FILTERS (data now loaded) ---
all_bus = ["All"] + sorted(df['business_unit'].unique().tolist())
selected_bu = st.sidebar.selectbox("Business Unit", all_bus)
min_jobs    = st.sidebar.slider("Min jobs (filter noise)", 10, 100, 20)
risk_filter = st.sidebar.selectbox(
    "Risk Level",
    ["All", "🔴 High (>20%)", "🟡 Medium (5–20%)", "🟢 Low (<5%)"]
)

# --- KPI ROW ---
st.markdown("---")
total_jobs       = int(df['total_jobs'].sum())
total_cancelled  = int(df['cancelled_jobs'].sum())
overall_rate     = round(total_cancelled / total_jobs * 100, 1) if total_jobs > 0 else 0
highest_rate_row = df.iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Jobs (since 2020)", f"{total_jobs:,}")
col2.metric("Total Cancellations",     f"{total_cancelled:,}")
col3.metric("Overall Cancel Rate",     f"{overall_rate}%")
col4.metric("Highest Cancel Rate",     f"{highest_rate_row['job_type']} — {highest_rate_row['cancellation_rate_pct']}%")

st.markdown("---")

# --- APPLY FILTERS ---
df_filtered = df[df['total_jobs'] >= min_jobs].copy()
if selected_bu != "All":
    df_filtered = df_filtered[df_filtered['business_unit'] == selected_bu]
if risk_filter == "🔴 High (>20%)":
    df_filtered = df_filtered[df_filtered['cancellation_rate_pct'] > 20]
elif risk_filter == "🟡 Medium (5–20%)":
    df_filtered = df_filtered[
        (df_filtered['cancellation_rate_pct'] >= 5) &
        (df_filtered['cancellation_rate_pct'] <= 20)
    ]
elif risk_filter == "🟢 Low (<5%)":
    df_filtered = df_filtered[df_filtered['cancellation_rate_pct'] < 5]

def risk_label(rate):
    if rate > 20:   return "🔴 High"
    elif rate >= 5: return "🟡 Medium"
    else:           return "🟢 Low"

df_filtered['risk'] = df_filtered['cancellation_rate_pct'].apply(risk_label)
df_filtered['overbook_multiplier'] = (1 + df_filtered['cancellation_rate_pct'] / 100).round(2)

# --- CHART 1: Cancel Rate by Job Type ---
st.subheader("📊 Cancellation Rate by Job Type")
fig1 = px.bar(
    df_filtered.sort_values('cancellation_rate_pct', ascending=True).tail(20),
    x='cancellation_rate_pct', y='job_type',
    color='cancellation_rate_pct', orientation='h',
    color_continuous_scale='RdYlGn_r',
    labels={'cancellation_rate_pct': 'Cancel Rate %', 'job_type': 'Job Type'},
    hover_data=['business_unit', 'total_jobs', 'cancelled_jobs', 'avg_days_to_cancellation']
)
fig1.update_layout(
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    yaxis={'categoryorder': 'total ascending'}, coloraxis_showscale=False
)
st.plotly_chart(fig1, use_container_width=True)

# --- CHART 2 + 3 SIDE BY SIDE ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📅 Cancel Rate by Month")
    df_monthly_filtered = df_monthly.copy()
    if selected_bu != "All":
        df_monthly_filtered = df_monthly_filtered[df_monthly_filtered['business_unit'] == selected_bu]
    else:
        df_monthly_filtered = df_monthly_filtered.groupby('month').agg(
            total_jobs=('total_jobs', 'sum'),
            cancelled_jobs=('cancelled_jobs', 'sum')
        ).reset_index()
        df_monthly_filtered['cancellation_rate_pct'] = round(
            df_monthly_filtered['cancelled_jobs'] * 100 / df_monthly_filtered['total_jobs'], 2
        )
    fig2 = px.line(
        df_monthly_filtered, x='month', y='cancellation_rate_pct',
        labels={'cancellation_rate_pct': 'Cancel Rate %', 'month': 'Month'},
        markers=True, color_discrete_sequence=['#E74C3C']
    )
    fig2.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig2, use_container_width=True)

with col2:
    st.subheader("📆 Cancel Rate by Day of Week")
    fig3 = px.bar(
        df_dow, x='day_of_week', y='cancellation_rate_pct',
        color='cancellation_rate_pct', color_continuous_scale='RdYlGn_r',
        labels={'cancellation_rate_pct': 'Cancel Rate %', 'day_of_week': 'Day'}
    )
    fig3.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        coloraxis_showscale=False
    )
    st.plotly_chart(fig3, use_container_width=True)

# --- CANCEL REASONS ---
st.markdown("---")
st.subheader("💬 Cancellation Reasons")

col1, col2 = st.columns(2)
with col1:
    df_reason_grouped = df_reasons.groupby('cancel_reason')['total_cancellations'].sum().reset_index()
    df_reason_grouped = df_reason_grouped.sort_values('total_cancellations', ascending=True)
    fig4 = px.bar(
        df_reason_grouped, x='total_cancellations', y='cancel_reason',
        orientation='h', color='total_cancellations', color_continuous_scale='Reds',
        labels={'total_cancellations': 'Cancellations', 'cancel_reason': 'Reason'}
    )
    fig4.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        coloraxis_showscale=False, yaxis={'categoryorder': 'total ascending'}
    )
    st.plotly_chart(fig4, use_container_width=True)

with col2:
    st.markdown("**Reasons by Business Unit**")
    df_reason_bu = df_reasons.groupby(['cancel_reason', 'business_unit'])['total_cancellations'].sum().reset_index()
    fig5 = px.bar(
        df_reason_bu, x='total_cancellations', y='cancel_reason',
        color='business_unit', orientation='h',
        labels={'total_cancellations': 'Cancellations', 'cancel_reason': 'Reason', 'business_unit': 'Business Unit'}
    )
    fig5.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        yaxis={'categoryorder': 'total ascending'}
    )
    st.plotly_chart(fig5, use_container_width=True)

# --- OVERBOOKING MODEL ---
st.markdown("---")
st.subheader("🔄 Overbooking Multiplier — How Many Extra Jobs to Book")
st.caption("If a job type cancels 20% of the time, book 1.2x the slots — so when cancellations happen, the day stays full.")

df_overbook = df_filtered[df_filtered['cancellation_rate_pct'] > 0].sort_values(
    'cancellation_rate_pct', ascending=False
).head(15)

fig6 = px.bar(
    df_overbook, x='job_type', y='overbook_multiplier',
    color='cancellation_rate_pct', color_continuous_scale='RdYlGn_r',
    labels={
        'overbook_multiplier': 'Overbook Multiplier',
        'job_type': 'Job Type',
        'cancellation_rate_pct': 'Cancel Rate %'
    },
    hover_data=['business_unit', 'total_jobs', 'cancellation_rate_pct']
)
fig6.add_hline(y=1.0, line_dash="dash", line_color="gray", annotation_text="No overbooking (1.0x)")
fig6.update_layout(
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    xaxis_tickangle=-35
)
st.plotly_chart(fig6, use_container_width=True)

# --- FULL TABLE ---
st.markdown("---")
st.subheader("📋 Full Cancellation Data Table")
st.dataframe(
    df_filtered[[
        'job_type', 'business_unit', 'total_jobs', 'cancelled_jobs',
        'cancellation_rate_pct', 'avg_days_to_cancellation',
        'overbook_multiplier', 'risk'
    ]].rename(columns={
        'job_type':                 'Job Type',
        'business_unit':            'Business Unit',
        'total_jobs':               'Total Jobs',
        'cancelled_jobs':           'Cancelled',
        'cancellation_rate_pct':    'Cancel Rate %',
        'avg_days_to_cancellation': 'Avg Days to Cancel',
        'overbook_multiplier':      'Overbook Multiplier',
        'risk':                     'Risk Level'
    }),
    use_container_width=True, hide_index=True
)

# --- RECENT CANCELLATIONS LOG ---
st.markdown("---")
st.subheader("🕐 Last 100 Cancellations")
st.caption("Most recent cancellations with the reason and notes written by staff.")
st.dataframe(
    df_recent.rename(columns={
        'job_number':     'Job #',
        'customer':       'Customer',
        'job_type':       'Job Type',
        'business_unit':  'Business Unit',
        'job_created':    'Job Created',
        'cancelled_on':   'Cancelled On',
        'hours_to_cancel':'Hours to Cancel',
        'cancel_reason':  'Reason',
        'notes':          'Staff Notes'
    }),
    use_container_width=True, hide_index=True
)

# --- DOWNLOAD ---
st.markdown("---")
csv = df_filtered.to_csv(index=False)
st.download_button(
    label="⬇️ Download Cancellation Data as CSV",
    data=csv,
    file_name="cancellation_analysis.csv",
    mime="text/csv"
)