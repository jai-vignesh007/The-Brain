import streamlit as st
import pandas as pd
import plotly.express as px
from google.cloud import bigquery
from google.oauth2 import service_account
from utils import get_client, render_sidebar
# --- CONFIG ---
PROJECT_ID = "the-brain-487614"

st.set_page_config(
    page_title="CallRail Dashboard",
    page_icon="📞",
    layout="wide"
)

# --- CLIENT ---
client = get_client()

#--- SIDEBAR (always first) ---
render_sidebar()
# --- TITLE ---
st.title("📞 CallRail Performance Dashboard")
st.markdown("Live data from BigQuery")

# --- TEST CONNECTION ---
st.subheader("Testing BigQuery Connection...")
try:
    test = client.query(
        "SELECT COUNT(*) as total FROM `the-brain-487614.analytics.callrail_daily_summary`"
    ).to_dataframe()
    st.success(f"✅ Connected! Found {test['total'][0]} days of data.")
except Exception as e:
    st.error(f"❌ Connection failed: {e}")

# --- LOAD DATA ---
@st.cache_data(ttl=3600)
def load_daily_summary():
    return client.query("""
        SELECT * FROM `the-brain-487614.analytics.callrail_daily_summary`
        ORDER BY date DESC
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_channel_performance():
    return client.query("""
        SELECT * FROM `the-brain-487614.analytics.callrail_channel_performance`
        ORDER BY total_leads DESC
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_hourly_heatmap():
    return client.query("""
        SELECT * FROM `the-brain-487614.analytics.callrail_hourly_heatmap`
        ORDER BY call_day_of_week, call_hour
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_geo_summary():
    return client.query("""
        SELECT * FROM `the-brain-487614.analytics.callrail_geo_summary`
        ORDER BY total_calls DESC
    """).to_dataframe()

@st.cache_data(ttl=3600)
def load_tracker_health():
    return client.query("""
        SELECT * FROM `the-brain-487614.analytics.callrail_tracker_health`
        ORDER BY total_calls DESC
    """).to_dataframe()

df_daily   = load_daily_summary()
df_channel = load_channel_performance()
df_heatmap = load_hourly_heatmap()
df_geo     = load_geo_summary()
df_tracker = load_tracker_health()

# --- KPI ROW ---
st.markdown("---")

total_calls    = int(df_daily['total_calls'].sum())
total_forms    = int(df_daily['total_forms'].sum())
total_leads    = int(df_daily['total_leads'].sum())
missed_calls   = int(df_daily['missed_calls'].sum())
answered_calls = int(df_daily['answered_calls'].sum())
avg_answer_rate = round((answered_calls / total_calls * 100), 1) if total_calls > 0 else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📞 Total Calls",      f"{total_calls:,}")
col2.metric("📋 Form Submissions", f"{total_forms:,}")
col3.metric("🎯 Total Leads",      f"{total_leads:,}")
col4.metric("❌ Missed Calls",     f"{missed_calls:,}")
col5.metric("✅ Answer Rate",      f"{avg_answer_rate}%")

# --- DATE FILTER ---
st.markdown("---")
st.subheader("📈 Call Volume Trend")

df_daily['date'] = pd.to_datetime(df_daily['date']).dt.date
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", value=df_daily['date'].min())
with col2:
    end_date = st.date_input("End Date", value=df_daily['date'].max())

mask = (df_daily['date'] >= start_date) & (df_daily['date'] <= end_date)
df_filtered = df_daily[mask].sort_values('date')

# --- TREND CHART ---
fig = px.line(
    df_filtered,
    x='date',
    y=['total_calls', 'answered_calls', 'missed_calls', 'total_forms'],
    labels={'value': 'Count', 'date': 'Date', 'variable': 'Metric'},
    color_discrete_map={
        'total_calls':    '#4C9BE8',
        'answered_calls': '#2ECC71',
        'missed_calls':   '#E74C3C',
        'total_forms':    '#F39C12'
    }
)
fig.update_layout(
    legend_title="Metric",
    hovermode="x unified",
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
)
st.plotly_chart(fig, use_container_width=True)

# --- CHANNEL PERFORMANCE ---
st.markdown("---")
st.subheader("📡 Channel Performance")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Total Leads by Channel**")
    fig_leads = px.bar(
        df_channel.head(10),
        x='total_leads', y='source_channel', orientation='h',
        color='total_leads', color_continuous_scale='Blues',
        labels={'total_leads': 'Total Leads', 'source_channel': 'Channel'}
    )
    fig_leads.update_layout(
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        yaxis={'categoryorder': 'total ascending'}
    )
    st.plotly_chart(fig_leads, use_container_width=True)

with col2:
    st.markdown("**Answer Rate & Lead Rate by Channel**")
    fig_rates = px.bar(
        df_channel.head(10),
        x='source_channel',
        y=['answer_rate_pct', 'lead_rate_pct', 'engagement_rate_pct'],
        barmode='group',
        labels={'value': 'Rate (%)', 'source_channel': 'Channel', 'variable': 'Metric'},
        color_discrete_map={
            'answer_rate_pct':     '#2ECC71',
            'lead_rate_pct':       '#4C9BE8',
            'engagement_rate_pct': '#F39C12'
        }
    )
    fig_rates.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        xaxis_tickangle=-45
    )
    st.plotly_chart(fig_rates, use_container_width=True)

st.markdown("**Full Channel Breakdown**")
st.dataframe(
    df_channel[[
        'source_channel', 'total_calls', 'total_forms', 'total_leads',
        'answered_calls', 'missed_calls', 'qualified_leads',
        'answer_rate_pct', 'lead_rate_pct', 'engagement_rate_pct',
        'avg_call_duration_seconds'
    ]].rename(columns={
        'source_channel':            'Channel',
        'total_calls':               'Calls',
        'total_forms':               'Forms',
        'total_leads':               'Total Leads',
        'answered_calls':            'Answered',
        'missed_calls':              'Missed',
        'qualified_leads':           'Qualified',
        'answer_rate_pct':           'Answer Rate %',
        'lead_rate_pct':             'Lead Rate %',
        'engagement_rate_pct':       'Engagement %',
        'avg_call_duration_seconds': 'Avg Duration (sec)'
    }),
    use_container_width=True, hide_index=True
)

# --- HOURLY HEATMAP ---
st.markdown("---")
st.subheader("🕐 Peak Call Hours Heatmap")

day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Total Calls by Hour & Day**")
    df_pivot = df_heatmap.pivot(index='day_name', columns='hour_label', values='total_calls')
    df_pivot = df_pivot.reindex(day_order)
    fig_heat = px.imshow(
        df_pivot, color_continuous_scale='Blues',
        labels=dict(x="Hour", y="Day", color="Calls"), aspect='auto'
    )
    fig_heat.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_heat, use_container_width=True)

with col2:
    st.markdown("**Missed Calls by Hour & Day**")
    df_pivot_missed = df_heatmap.pivot(index='day_name', columns='hour_label', values='missed_calls')
    df_pivot_missed = df_pivot_missed.reindex(day_order)
    fig_missed = px.imshow(
        df_pivot_missed, color_continuous_scale='Reds',
        labels=dict(x="Hour", y="Day", color="Missed"), aspect='auto'
    )
    fig_missed.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_missed, use_container_width=True)

st.caption("🔵 Darker blue = more calls  |  🔴 Darker red = more missed calls = staffing gap")

# --- GEOGRAPHIC BREAKDOWN ---
st.markdown("---")
st.subheader("🗺️ Geographic Intelligence")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**Top 15 Cities by Call Volume**")
    fig_geo = px.bar(
        df_geo.head(15),
        x='total_calls', y='customer_city', orientation='h',
        color='lead_rate_pct', color_continuous_scale='Blues',
        labels={'total_calls': 'Total Calls', 'customer_city': 'City', 'lead_rate_pct': 'Lead Rate %'}
    )
    fig_geo.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig_geo, use_container_width=True)

with col2:
    st.markdown("**Top 15 Cities by Lead Rate %**")
    df_geo_quality = df_geo[df_geo['total_calls'] >= 5].sort_values(
        'lead_rate_pct', ascending=False
    ).head(15)
    fig_quality = px.bar(
        df_geo_quality,
        x='lead_rate_pct', y='customer_city', orientation='h',
        color='total_calls', color_continuous_scale='Greens',
        labels={'lead_rate_pct': 'Lead Rate %', 'customer_city': 'City', 'total_calls': 'Total Calls'}
    )
    fig_quality.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig_quality, use_container_width=True)

st.markdown("**Full Geographic Breakdown**")
st.dataframe(
    df_geo[[
        'customer_state', 'customer_city', 'total_calls',
        'answered_calls', 'missed_calls', 'qualified_leads',
        'lead_rate_pct', 'engagement_rate_pct', 'avg_duration_seconds'
    ]].rename(columns={
        'customer_state':      'State',
        'customer_city':       'City',
        'total_calls':         'Total Calls',
        'answered_calls':      'Answered',
        'missed_calls':        'Missed',
        'qualified_leads':     'Qualified Leads',
        'lead_rate_pct':       'Lead Rate %',
        'engagement_rate_pct': 'Engagement %',
        'avg_duration_seconds':'Avg Duration (sec)'
    }),
    use_container_width=True, hide_index=True
)

# --- TRACKER HEALTH ---
st.markdown("---")
st.subheader("📡 Tracker Health")

total_trackers  = len(df_tracker)
active_trackers = len(df_tracker[df_tracker['status'] == 'active'])
gclid_capable   = len(df_tracker[df_tracker['is_gclid_capable'] == True])
broken_gclid    = len(df_tracker[
    (df_tracker['is_gclid_capable'] == True) &
    (df_tracker['gclid_capture_rate_pct'] == 0)
])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Trackers",  total_trackers)
col2.metric("Active Trackers", active_trackers)
col3.metric("GCLID Capable",   gclid_capable)
col4.metric("⚠️ GCLID Broken", broken_gclid,
            delta=f"{broken_gclid} need fixing", delta_color="inverse")

st.markdown("**Tracker Details**")
st.dataframe(
    df_tracker[[
        'tracker_name', 'tracker_type', 'source_type',
        'status', 'is_gclid_capable', 'tracker_health_status',
        'total_calls', 'answered_calls', 'missed_calls',
        'qualified_leads', 'calls_with_gclid', 'gclid_capture_rate_pct',
        'answer_rate_pct'
    ]].rename(columns={
        'tracker_name':           'Tracker',
        'tracker_type':           'Type',
        'source_type':            'Source Type',
        'status':                 'Status',
        'is_gclid_capable':       'GCLID Capable',
        'tracker_health_status':  'Health',
        'total_calls':            'Total Calls',
        'answered_calls':         'Answered',
        'missed_calls':           'Missed',
        'qualified_leads':        'Qualified Leads',
        'calls_with_gclid':       'Calls w/ GCLID',
        'gclid_capture_rate_pct': 'GCLID Rate %',
        'answer_rate_pct':        'Answer Rate %'
    }),
    use_container_width=True, hide_index=True
)

st.markdown("**Call Volume per Tracker**")
fig_tracker = px.bar(
    df_tracker[df_tracker['total_calls'] > 0],
    x='tracker_name', y='total_calls',
    color='tracker_health_status',
    labels={
        'tracker_name':          'Tracker',
        'total_calls':           'Total Calls',
        'tracker_health_status': 'Health Status'
    },
    color_discrete_map={
        '✅ Healthy':             '#2ECC71',
        '⚠️ GCLID Not Capturing': '#E74C3C',
        'Static Tracker':         '#4C9BE8',
        'Disabled':               '#95A5A6'
    }
)
fig_tracker.update_layout(
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    xaxis_tickangle=-45
)
st.plotly_chart(fig_tracker, use_container_width=True)