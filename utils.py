import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_ID = "the-brain-487614"

@st.cache_resource
def get_client():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    return bigquery.Client(project=PROJECT_ID, credentials=creds)


def apply_global_css():
    st.markdown("""
    <style>
    [data-testid="stSidebarNav"] { display: none; }
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    section[data-testid="stSidebar"] { background: #1a1f2e; }
    section[data-testid="stSidebar"] * { color: #c8cdd8 !important; }
    h1 { color: #ffffff !important; font-weight: 700 !important; }
    h3 { color: rgba(255,255,255,0.9) !important; font-weight: 600 !important;
         margin-top: 2rem !important; padding-bottom: 0.4rem;
         border-bottom: 2px solid rgba(255,255,255,0.15); }
    div[data-testid="stMetric"] { background: transparent; border: none;
         border-left: 3px solid rgba(255,255,255,0.25); border-radius: 0;
         padding: 4px 0 4px 16px; }
    div[data-testid="stMetric"] label { color: rgba(255,255,255,0.6) !important;
         font-size: 0.78rem !important; font-weight: 600 !important;
         letter-spacing: 0.04em; text-transform: uppercase; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
         color: #ffffff !important; font-weight: 700 !important; font-size: 1.3rem !important; }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar():
    apply_global_css()
    with st.sidebar:
        st.markdown("### ⚡ The Brain")
        st.caption("Premier Energy Solutions")
        st.markdown("---")
        st.page_link("dashboard.py",                          label="🏠  Home")
        st.page_link("pages/6_Profit.py",                     label="💰  Gross Profit & KPIs")
        st.page_link("pages/4_Google_Ads.py",                 label="📊  Google Ads Performance")
        st.page_link("pages/5_Google_Ads_Intelligence.py",    label="🧠  Google Ads Intelligence")
        st.page_link("pages/7_Google_Ads_explorer.py",        label="🔍  Google Ads Explorer")
        st.page_link("pages/3_Cancellation_Analysis.py",      label="❌  Cancellation Analysis")
        st.page_link("pages/8_CallRail.py",                   label="📞  CallRail")
        st.page_link("pages/2_ServiceTitan_Explorer.py",      label="🗄️  Data Explorer")
        st.markdown("---")
        st.caption("Refreshes every hour · BigQuery")