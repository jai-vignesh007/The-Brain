import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta
from utils import get_client, render_sidebar

# --- PAGE SETUP ---
st.set_page_config(page_title="Gross Profit & KPIs", page_icon="💰", layout="wide")

# --- SIDEBAR ---
render_sidebar()
st.sidebar.markdown("---")
st.sidebar.subheader("Date Filter")
start_date = st.sidebar.date_input("Start", value=date.today() - timedelta(days=90))
end_date   = st.sidebar.date_input("End",   value=date.today())
if start_date > end_date:
    st.sidebar.error("Start date must be before end date.")
    st.stop()
st.sidebar.markdown("---")
page = st.sidebar.radio("Section", ["GP Summary", "Technicians", "Calls"])

# --- CLIENT ---
PROJECT = "the-brain-487614"
client  = get_client()

def run_query(sql):
    return client.query(sql).to_dataframe()

# --- CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { background: #1a1f2e; }
section[data-testid="stSidebar"] * { color: #c8cdd8 !important; }
section[data-testid="stSidebar"] .stRadio label:hover { color: #fff !important; }
div[data-testid="stMetric"] {
    background: transparent; border: none;
    border-left: 3px solid rgba(255,255,255,0.25);
    border-radius: 0; padding: 4px 0 4px 16px;
}
div[data-testid="stMetric"] label {
    color: rgba(255,255,255,0.6) !important; font-size: 0.78rem !important;
    font-weight: 600 !important; letter-spacing: 0.04em; text-transform: uppercase;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #ffffff !important; font-weight: 700 !important;
    font-size: clamp(1.1rem, 1.8vw, 1.45rem) !important;
    white-space: nowrap !important; line-height: 1.1 !important;
}
div[data-testid="stDataFrame"] { border: 1px solid #e8eaef; border-radius: 10px; overflow: hidden; }
h3 { color: rgba(255,255,255,0.9) !important; font-weight: 600 !important;
     margin-top: 2rem !important; padding-bottom: 0.4rem;
     border-bottom: 2px solid rgba(255,255,255,0.15); }
h1 { color: #ffffff !important; font-weight: 700 !important; font-size: 2rem !important;
     border-bottom: 3px solid rgba(255,255,255,0.3);
     padding-bottom: 0.5rem !important; margin-bottom: 0.5rem !important; }
div[data-testid="stCaptionContainer"] { color: rgba(255,255,255,0.5) !important; font-size: 0.82rem !important; }
div[data-testid="stDownloadButton"] > button {
    background: transparent !important; color: rgba(255,255,255,0.7) !important;
    border: 1px solid rgba(255,255,255,0.2) !important; border-radius: 6px !important;
    padding: 0.3rem 1rem !important; font-size: 0.8rem !important; font-weight: 500 !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    background: rgba(255,255,255,0.08) !important; color: #ffffff !important;
    border-color: rgba(255,255,255,0.4) !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# GP SUMMARY
# ─────────────────────────────────────────────
if page == "GP Summary":
    st.title("Gross Profit Summary")
    st.markdown("")

    bu_options = run_query(f"""
        SELECT DISTINCT j.business_unit_id,
               COALESCE(bu.name, CAST(j.business_unit_id AS STRING)) AS bu_name
        FROM `{PROJECT}.servicetitan.job` AS j
        LEFT JOIN `{PROJECT}.servicetitan.business_unit` AS bu ON j.business_unit_id = bu.id
        WHERE j._fivetran_deleted = FALSE
          AND j.job_status = 'Completed'
          AND j.completed_on BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY bu_name
    """)
    bu_map      = dict(zip(bu_options["bu_name"], bu_options["business_unit_id"]))
    dept_filter = st.selectbox("Department", ["All Departments"] + list(bu_map.keys()))
    dept_clause = f"AND j.business_unit_id = {bu_map[dept_filter]}" if dept_filter != "All Departments" else ""

    kpi = run_query(f"""
        WITH completed_jobs AS (
            SELECT
                j.id AS job_id,
                j.project_id,
                j.completed_on,
                j.business_unit_id,
                COALESCE(fin.gross_profit, 0) AS gross_profit,
                COALESCE(fin.revenue, 0) AS revenue
            FROM `{PROJECT}.servicetitan.job` AS j
            LEFT JOIN (
                SELECT
                    i.job_id,
                    SUM(ii.total - COALESCE(ii.total_cost, 0)) AS gross_profit,
                    SUM(ii.total) AS revenue
                FROM `{PROJECT}.servicetitan.invoice` AS i
                JOIN `{PROJECT}.servicetitan.invoice_item` AS ii ON i.id = ii.invoice_id
                WHERE i._fivetran_deleted = FALSE
                  AND i.active = TRUE
                  AND ii._fivetran_deleted = FALSE
                  AND ii.active = TRUE
                GROUP BY i.job_id
            ) AS fin ON j.id = fin.job_id
            WHERE j._fivetran_deleted = FALSE
              AND j.job_status = 'Completed'
              AND j.completed_on BETWEEN '{start_date}' AND '{end_date}'
              {dept_clause}
        ),
        job_totals AS (
            SELECT
                SUM(gross_profit) AS gp_no_labor,
                SUM(revenue)      AS total_revenue,
                (SELECT COUNT(*) FROM (
                    SELECT COALESCE(project_id, job_id) AS pk
                    FROM completed_jobs
                    GROUP BY pk
                    HAVING SUM(revenue) > 0
                )) AS total_projects
            FROM completed_jobs
        ),
        job_labor AS (
            SELECT
                SUM(p.burden_rate * TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS job_labor_cost
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN completed_jobs AS j ON ts.job_id = j.job_id
            JOIN `{PROJECT}.servicetitan.payroll` AS p
                ON ts.technician_id = p.employee_id
                AND DATE(ts.dispatched_on) BETWEEN DATE(p.started_on) AND DATE(p.ended_on)
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
        ),
        dept_job_hours AS (
            SELECT
                ts.technician_id,
                SUM(TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS dept_hours
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN completed_jobs AS j ON ts.job_id = j.job_id
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
            GROUP BY ts.technician_id
        ),
        all_job_hours AS (
            SELECT
                ts.technician_id,
                SUM(TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS total_hours
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN `{PROJECT}.servicetitan.job` AS aj
                ON ts.job_id = aj.id
                AND aj._fivetran_deleted = FALSE
                AND aj.job_status = 'Completed'
                AND aj.completed_on BETWEEN '{start_date}' AND '{end_date}'
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
              AND ts.technician_id IN (SELECT technician_id FROM dept_job_hours)
            GROUP BY ts.technician_id
        ),
        non_job_labor AS (
            SELECT
                SUM(
                    p.burden_rate * (
                        SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                        SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0
                    )
                    * djh.dept_hours / ajh.total_hours
                ) AS non_job_labor_cost
            FROM `{PROJECT}.servicetitan.non_job_appointment` AS nja
            JOIN dept_job_hours AS djh ON nja.technician_id = djh.technician_id
            JOIN all_job_hours AS ajh ON nja.technician_id = ajh.technician_id
            JOIN `{PROJECT}.servicetitan.payroll` AS p
                ON nja.technician_id = p.employee_id
                AND DATE(nja.start) BETWEEN DATE(p.started_on) AND DATE(p.ended_on)
            JOIN `{PROJECT}.servicetitan.technician` AS t ON nja.technician_id = t.id
            WHERE nja.active = TRUE
              AND nja._fivetran_deleted = FALSE
              AND nja.start BETWEEN '{start_date}' AND '{end_date}'
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
              AND LOWER(nja.name) NOT LIKE '%off%'
              AND LOWER(nja.name) NOT LIKE '%pto%'
              AND LOWER(nja.name) NOT LIKE '%vacation%'
              AND LOWER(nja.name) NOT LIKE '%sick%'
              AND LOWER(nja.name) NOT LIKE '%funeral%'
              AND LOWER(nja.name) NOT LIKE '%injured%'
              AND LOWER(nja.name) NOT LIKE '%jury%'
              AND LOWER(nja.name) NOT LIKE '%not in%'
              AND LOWER(nja.name) NOT LIKE '%no mas%'
              AND LOWER(nja.name) NOT LIKE '%out%'
              AND LOWER(nja.name) NOT LIKE '%no schedule%'
        )
        SELECT
            jt.gp_no_labor - COALESCE(jl.job_labor_cost, 0) - COALESCE(njl.non_job_labor_cost, 0) AS total_gp,
            jt.gp_no_labor,
            jt.total_revenue,
            jt.total_projects,
            jt.total_revenue - jt.gp_no_labor AS item_cost,
            COALESCE(jl.job_labor_cost, 0) + COALESCE(njl.non_job_labor_cost, 0) AS labor_cost,
            COALESCE(jl.job_labor_cost, 0) AS job_labor_cost,
            COALESCE(njl.non_job_labor_cost, 0) AS non_job_labor_cost
        FROM job_totals AS jt, job_labor AS jl, non_job_labor AS njl
    """)

    total_gp           = float(kpi["total_gp"].iloc[0] or 0)
    gp_before_labor    = float(kpi["gp_no_labor"].iloc[0] or 0)
    total_rev          = float(kpi["total_revenue"].iloc[0] or 0)
    total_projects     = int(kpi["total_projects"].iloc[0] or 0)
    item_cost          = float(kpi["item_cost"].iloc[0] or 0)
    labor_cost         = float(kpi["labor_cost"].iloc[0] or 0)
    job_labor_cost     = float(kpi["job_labor_cost"].iloc[0] or 0)
    non_job_labor_cost = float(kpi["non_job_labor_cost"].iloc[0] or 0)
    margin             = (total_gp / total_rev * 100) if total_rev else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Revenue",        f"${total_rev:,.0f}")
    c2.metric("Material / Item Cost", f"${item_cost:,.0f}")
    c3.metric("GP Before Labor",      f"${gp_before_labor:,.0f}")
    c4.metric("Total Gross Profit",   f"${total_gp:,.0f}")
    c5.metric("GP Margin",            f"{margin:.1f}%")

    st.markdown("")
    c6, c7, c8, c9, c10 = st.columns(5)
    c6.metric("Total Labor Cost",     f"${labor_cost:,.0f}")
    c7.metric("Job Labor",            f"${job_labor_cost:,.0f}")
    c8.metric("Non-Job Labor",        f"${non_job_labor_cost:,.0f}")
    c9.metric("Completed Projects",   f"{total_projects:,}")
    c10.metric("Avg Project Revenue", f"${total_rev / total_projects:,.0f}" if total_projects else "$0")

    st.markdown("")
    st.subheader("Gross Profit Over Time")
    weekly = run_query(f"""
        WITH completed_jobs AS (
            SELECT
                j.id AS job_id,
                j.project_id,
                j.completed_on,
                COALESCE(fin.gross_profit, 0) AS gross_profit,
                COALESCE(fin.revenue, 0) AS revenue
            FROM `{PROJECT}.servicetitan.job` AS j
            LEFT JOIN (
                SELECT
                    i.job_id,
                    SUM(ii.total - COALESCE(ii.total_cost, 0)) AS gross_profit,
                    SUM(ii.total) AS revenue
                FROM `{PROJECT}.servicetitan.invoice` AS i
                JOIN `{PROJECT}.servicetitan.invoice_item` AS ii ON i.id = ii.invoice_id
                WHERE i._fivetran_deleted = FALSE
                  AND i.active = TRUE
                  AND ii._fivetran_deleted = FALSE
                  AND ii.active = TRUE
                GROUP BY i.job_id
            ) AS fin ON j.id = fin.job_id
            WHERE j._fivetran_deleted = FALSE
              AND j.job_status = 'Completed'
              AND j.completed_on BETWEEN '{start_date}' AND '{end_date}'
              {dept_clause}
        ),
        weekly_project_counts AS (
            SELECT
                DATE_TRUNC(DATE(completed_on), WEEK(MONDAY)) AS week_start
            FROM completed_jobs
            GROUP BY week_start, COALESCE(project_id, job_id)
            HAVING SUM(revenue) > 0
        ),
        weekly_project_agg AS (
            SELECT week_start, COUNT(*) AS projects
            FROM weekly_project_counts
            GROUP BY week_start
        ),
        weekly_rev AS (
            SELECT
                DATE_TRUNC(DATE(completed_on), WEEK(MONDAY)) AS week_start,
                SUM(revenue) AS revenue,
                SUM(revenue - gross_profit) AS item_cost,
                SUM(gross_profit) AS gp_no_labor
            FROM completed_jobs
            GROUP BY week_start
        ),
        weekly_job_labor AS (
            SELECT
                DATE_TRUNC(DATE(j.completed_on), WEEK(MONDAY)) AS week_start,
                SUM(p.burden_rate * TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS job_labor_cost
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN completed_jobs AS j ON ts.job_id = j.job_id
            JOIN `{PROJECT}.servicetitan.payroll` AS p
                ON ts.technician_id = p.employee_id
                AND DATE(ts.dispatched_on) BETWEEN DATE(p.started_on) AND DATE(p.ended_on)
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
            GROUP BY week_start
        ),
        dept_job_hours AS (
            SELECT
                ts.technician_id,
                SUM(TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS dept_hours
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN completed_jobs AS j ON ts.job_id = j.job_id
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
            GROUP BY ts.technician_id
        ),
        all_job_hours AS (
            SELECT
                ts.technician_id,
                SUM(TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS total_hours
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN `{PROJECT}.servicetitan.job` AS aj
                ON ts.job_id = aj.id
                AND aj._fivetran_deleted = FALSE
                AND aj.job_status = 'Completed'
                AND aj.completed_on BETWEEN '{start_date}' AND '{end_date}'
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
              AND ts.technician_id IN (SELECT technician_id FROM dept_job_hours)
            GROUP BY ts.technician_id
        ),
        weekly_non_job_labor AS (
            SELECT
                DATE_TRUNC(DATE(nja.start), WEEK(MONDAY)) AS week_start,
                SUM(
                    p.burden_rate * (
                        SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                        SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0
                    )
                    * djh.dept_hours / NULLIF(ajh.total_hours, 0)
                ) AS non_job_labor_cost
            FROM `{PROJECT}.servicetitan.non_job_appointment` AS nja
            JOIN dept_job_hours AS djh ON nja.technician_id = djh.technician_id
            JOIN all_job_hours AS ajh ON nja.technician_id = ajh.technician_id
            JOIN `{PROJECT}.servicetitan.payroll` AS p
                ON nja.technician_id = p.employee_id
                AND DATE(nja.start) BETWEEN DATE(p.started_on) AND DATE(p.ended_on)
            JOIN `{PROJECT}.servicetitan.technician` AS t ON nja.technician_id = t.id
            WHERE nja.active = TRUE
              AND nja._fivetran_deleted = FALSE
              AND nja.start BETWEEN '{start_date}' AND '{end_date}'
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
              AND LOWER(nja.name) NOT LIKE '%off%'
              AND LOWER(nja.name) NOT LIKE '%pto%'
              AND LOWER(nja.name) NOT LIKE '%vacation%'
              AND LOWER(nja.name) NOT LIKE '%sick%'
              AND LOWER(nja.name) NOT LIKE '%funeral%'
              AND LOWER(nja.name) NOT LIKE '%injured%'
              AND LOWER(nja.name) NOT LIKE '%jury%'
              AND LOWER(nja.name) NOT LIKE '%not in%'
              AND LOWER(nja.name) NOT LIKE '%no mas%'
              AND LOWER(nja.name) NOT LIKE '%out%'
              AND LOWER(nja.name) NOT LIKE '%no schedule%'
            GROUP BY week_start
        ),
        all_weeks AS (
            SELECT week_start FROM weekly_rev
            UNION DISTINCT
            SELECT week_start FROM weekly_job_labor
            UNION DISTINCT
            SELECT week_start FROM weekly_non_job_labor
        )
        SELECT
            aw.week_start,
            COALESCE(wr.revenue, 0) AS revenue,
            COALESCE(wr.item_cost, 0) AS item_cost,
            COALESCE(wr.gp_no_labor, 0) AS gp_no_labor,
            COALESCE(wjl.job_labor_cost, 0) AS job_labor_cost,
            COALESCE(wnjl.non_job_labor_cost, 0) AS non_job_labor_cost,
            COALESCE(wjl.job_labor_cost, 0) + COALESCE(wnjl.non_job_labor_cost, 0) AS labor_cost,
            COALESCE(wr.gp_no_labor, 0) - COALESCE(wjl.job_labor_cost, 0) - COALESCE(wnjl.non_job_labor_cost, 0) AS gross_profit,
            COALESCE(wpa.projects, 0) AS projects
        FROM all_weeks AS aw
        LEFT JOIN weekly_rev AS wr ON aw.week_start = wr.week_start
        LEFT JOIN weekly_project_agg AS wpa ON aw.week_start = wpa.week_start
        LEFT JOIN weekly_job_labor AS wjl ON aw.week_start = wjl.week_start
        LEFT JOIN weekly_non_job_labor AS wnjl ON aw.week_start = wnjl.week_start
        ORDER BY aw.week_start DESC
    """)
    if not weekly.empty:
        weekly["week_start"] = pd.to_datetime(weekly["week_start"])
        gp_chart = (
            alt.Chart(weekly)
            .mark_line(point=True)
            .encode(
                x=alt.X("week_start:T", title="Week Starting", axis=alt.Axis(format="%m/%d/%Y", labelAngle=-25)),
                y=alt.Y("gross_profit:Q", title="Gross Profit"),
                tooltip=[
                    alt.Tooltip("week_start:T", title="Week Starting", format="%m/%d/%Y"),
                    alt.Tooltip("gross_profit:Q", title="Gross Profit", format=",.2f"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(gp_chart, use_container_width=True)

        st.markdown("")
        st.subheader("Weekly Breakdown")
        weekly_display = weekly[["week_start", "revenue", "item_cost", "gp_no_labor",
                                 "job_labor_cost", "non_job_labor_cost", "labor_cost",
                                 "gross_profit", "projects"]].copy()
        weekly_display["week_start"] = weekly_display["week_start"].dt.strftime("%m/%d/%Y")
        weekly_display["margin"] = (
            weekly_display["gross_profit"]
            .div(weekly_display["revenue"].where(weekly_display["revenue"] != 0))
            .mul(100)
            .replace([float("inf"), float("-inf")], 0)
            .fillna(0)
            .round(1)
        )
        weekly_display.columns = ["Week", "Revenue", "Material Cost", "GP Before Labor",
                                  "Job Labor", "Non-Job Labor", "Total Labor",
                                  "Gross Profit", "Projects", "Margin %"]
        for col in ["Revenue", "Material Cost", "GP Before Labor", "Job Labor",
                     "Non-Job Labor", "Total Labor", "Gross Profit"]:
            weekly_display[col] = weekly_display[col].round(0).astype(int)
        weekly_display["Projects"] = weekly_display["Projects"].astype(int)
        weekly_display.index = range(1, len(weekly_display) + 1)
        st.download_button(
            "Export CSV ↓",
            weekly_display.to_csv(index=False),
            file_name=f"weekly_breakdown_{dept_filter.lower().replace(' ', '_')}.csv",
            mime="text/csv",
        )
        st.dataframe(weekly_display, width="stretch", hide_index=True, column_config={
            "Revenue": st.column_config.NumberColumn(format="$%d"),
            "Material Cost": st.column_config.NumberColumn(format="$%d"),
            "GP Before Labor": st.column_config.NumberColumn(format="$%d"),
            "Job Labor": st.column_config.NumberColumn(format="$%d"),
            "Non-Job Labor": st.column_config.NumberColumn(format="$%d"),
            "Total Labor": st.column_config.NumberColumn(format="$%d"),
            "Gross Profit": st.column_config.NumberColumn(format="$%d"),
            "Margin %": st.column_config.NumberColumn(format="%.1f%%"),
        })
    else:
        st.info("No data for the selected range.")

    st.markdown("")
    st.subheader("Project Breakdown")
    project_detail = run_query(f"""
        WITH completed_jobs AS (
            SELECT
                j.id AS job_id,
                j.project_id,
                j.customer_id,
                j.job_type_id,
                j.completed_on,
                COALESCE(fin.revenue, 0) AS revenue,
                COALESCE(fin.material_cost, 0) AS material_cost,
                COALESCE(fin.gross_profit, 0) AS gross_profit
            FROM `{PROJECT}.servicetitan.job` AS j
            LEFT JOIN (
                SELECT
                    i.job_id,
                    SUM(ii.total) AS revenue,
                    SUM(COALESCE(ii.total_cost, 0)) AS material_cost,
                    SUM(ii.total - COALESCE(ii.total_cost, 0)) AS gross_profit
                FROM `{PROJECT}.servicetitan.invoice` AS i
                JOIN `{PROJECT}.servicetitan.invoice_item` AS ii ON i.id = ii.invoice_id
                WHERE i._fivetran_deleted = FALSE
                  AND i.active = TRUE
                  AND ii._fivetran_deleted = FALSE
                  AND ii.active = TRUE
                GROUP BY i.job_id
            ) AS fin ON j.id = fin.job_id
            WHERE j._fivetran_deleted = FALSE
              AND j.job_status = 'Completed'
              AND j.completed_on BETWEEN '{start_date}' AND '{end_date}'
              {dept_clause}
        ),
        project_agg AS (
            SELECT
                COALESCE(cj.project_id, cj.job_id) AS project_key,
                MIN(c.name) AS customer,
                CASE
                    WHEN MAX(CASE WHEN jt.name = 'Generator Install' THEN 1 ELSE 0 END) = 1 THEN 'Generator Install'
                    WHEN MAX(CASE WHEN jt.name = 'HVAC Installation' THEN 1 ELSE 0 END) = 1 THEN 'HVAC Installation'
                    WHEN MAX(CASE WHEN jt.name = 'Electrical Install' THEN 1 ELSE 0 END) = 1 THEN 'Electrical Install'
                    WHEN MAX(CASE WHEN jt.name = 'Premier Playground Services' THEN 1 ELSE 0 END) = 1 THEN 'Premier Playground Services'
                    WHEN MAX(CASE WHEN jt.name = 'Panel Upgrade' THEN 1 ELSE 0 END) = 1 THEN 'Panel Upgrade'
                    WHEN MAX(CASE WHEN jt.name = 'Battery Storage Install' THEN 1 ELSE 0 END) = 1 THEN 'Battery Storage Install'
                    ELSE MIN(jt.name)
                END AS project_type,
                DATE(MAX(cj.completed_on)) AS completed_date,
                SUM(cj.revenue) AS revenue,
                SUM(cj.material_cost) AS material_cost,
                SUM(cj.gross_profit) AS gp_before_labor
            FROM completed_jobs AS cj
            LEFT JOIN `{PROJECT}.servicetitan.customer` AS c ON cj.customer_id = c.id
            LEFT JOIN `{PROJECT}.servicetitan.job_type` AS jt ON cj.job_type_id = jt.id
            GROUP BY project_key
        ),
        project_labor AS (
            SELECT
                COALESCE(cj.project_id, cj.job_id) AS project_key,
                SUM(p.burden_rate * TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS labor_cost
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN completed_jobs AS cj ON ts.job_id = cj.job_id
            JOIN `{PROJECT}.servicetitan.payroll` AS p
                ON ts.technician_id = p.employee_id
                AND DATE(ts.dispatched_on) BETWEEN DATE(p.started_on) AND DATE(p.ended_on)
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
            GROUP BY project_key
        )
        SELECT
            pa.project_key,
            pa.customer,
            pa.project_type,
            pa.completed_date,
            pa.revenue,
            pa.material_cost,
            COALESCE(pl.labor_cost, 0) AS labor_cost,
            pa.gp_before_labor - COALESCE(pl.labor_cost, 0) AS gp_after_job_labor,
            CASE WHEN pa.revenue > 0
                THEN ROUND((pa.gp_before_labor - COALESCE(pl.labor_cost, 0)) / pa.revenue * 100, 1)
                ELSE 0
            END AS margin
        FROM project_agg AS pa
        LEFT JOIN project_labor AS pl ON pa.project_key = pl.project_key
        WHERE pa.revenue > 0
        ORDER BY pa.revenue DESC
    """)
    if not project_detail.empty:
        pd_display = project_detail.copy()
        pd_display.columns = ["Project", "Customer", "Type", "Completed", "Revenue",
                               "Material Cost", "Job Labor", "GP After Job Labor", "Margin %"]
        for col in ["Revenue", "Material Cost", "Job Labor", "GP After Job Labor"]:
            pd_display[col] = pd_display[col].round(0).astype(int)

        all_types = sorted(pd_display["Type"].unique())
        fc1, fc2 = st.columns([3, 1])
        selected_types = fc1.multiselect("Filter by Type", all_types, default=[], key="project_type_filter")
        filtered = pd_display[pd_display["Type"].isin(selected_types)] if selected_types else pd_display
        fc2.metric("Projects", len(filtered))

        st.download_button(
            "Export Projects CSV ↓",
            filtered.to_csv(index=False),
            file_name="project_detail.csv",
            mime="text/csv",
        )
        st.dataframe(filtered, width="stretch", hide_index=True, column_config={
            "Revenue": st.column_config.NumberColumn(format="$%d"),
            "Material Cost": st.column_config.NumberColumn(format="$%d"),
            "Job Labor": st.column_config.NumberColumn(format="$%d"),
            "GP After Job Labor": st.column_config.NumberColumn(format="$%d"),
            "Margin %": st.column_config.NumberColumn(format="%.1f%%"),
        })

    st.markdown("")
    st.subheader("Non-Job Time Breakdown by Employee")
    nonjob_detail = run_query(f"""
        WITH completed_jobs AS (
            SELECT j.id AS job_id
            FROM `{PROJECT}.servicetitan.job` AS j
            WHERE j._fivetran_deleted = FALSE
              AND j.job_status = 'Completed'
              AND j.completed_on BETWEEN '{start_date}' AND '{end_date}'
              {dept_clause}
        ),
        dept_job_hours AS (
            SELECT
                ts.technician_id,
                SUM(TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS dept_hours
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN completed_jobs AS j ON ts.job_id = j.job_id
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
            GROUP BY ts.technician_id
        ),
        all_job_hours AS (
            SELECT
                ts.technician_id,
                SUM(TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS total_hours
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN `{PROJECT}.servicetitan.job` AS aj
                ON ts.job_id = aj.id
                AND aj._fivetran_deleted = FALSE
                AND aj.job_status = 'Completed'
                AND aj.completed_on BETWEEN '{start_date}' AND '{end_date}'
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
              AND ts.technician_id IN (SELECT technician_id FROM dept_job_hours)
            GROUP BY ts.technician_id
        )
        SELECT
            t.name AS employee,
            ROUND(SUM(CASE WHEN LOWER(nja.name) = 'shoptime' THEN
                (SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                 SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0)
                * djh.dept_hours / NULLIF(ajh.total_hours, 0)
            ELSE 0 END), 1) AS shop_time,
            ROUND(SUM(CASE WHEN LOWER(nja.name) LIKE '%travel%' OR LOWER(nja.name) LIKE '%drive home%' THEN
                (SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                 SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0)
                * djh.dept_hours / NULLIF(ajh.total_hours, 0)
            ELSE 0 END), 1) AS travel,
            ROUND(SUM(CASE WHEN LOWER(nja.name) LIKE '%meeting%' OR LOWER(nja.name) LIKE '%roundup%' THEN
                (SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                 SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0)
                * djh.dept_hours / NULLIF(ajh.total_hours, 0)
            ELSE 0 END), 1) AS meetings,
            ROUND(SUM(CASE WHEN LOWER(nja.name) LIKE '%training%' THEN
                (SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                 SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0)
                * djh.dept_hours / NULLIF(ajh.total_hours, 0)
            ELSE 0 END), 1) AS training,
            ROUND(SUM(CASE WHEN LOWER(nja.name) != 'shoptime'
                AND LOWER(nja.name) NOT LIKE '%travel%'
                AND LOWER(nja.name) NOT LIKE '%drive home%'
                AND LOWER(nja.name) NOT LIKE '%meeting%'
                AND LOWER(nja.name) NOT LIKE '%roundup%'
                AND LOWER(nja.name) NOT LIKE '%training%' THEN
                (SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                 SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0)
                * djh.dept_hours / NULLIF(ajh.total_hours, 0)
            ELSE 0 END), 1) AS other,
            ROUND(SUM(
                (SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                 SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0)
                * djh.dept_hours / NULLIF(ajh.total_hours, 0)
            ), 1) AS total_hours,
            ROUND(SUM(
                p.burden_rate *
                (SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                 SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0)
                * djh.dept_hours / NULLIF(ajh.total_hours, 0)
            ), 0) AS cost
        FROM `{PROJECT}.servicetitan.non_job_appointment` AS nja
        JOIN dept_job_hours AS djh ON nja.technician_id = djh.technician_id
        JOIN all_job_hours AS ajh ON nja.technician_id = ajh.technician_id
        JOIN `{PROJECT}.servicetitan.payroll` AS p
            ON nja.technician_id = p.employee_id
            AND DATE(nja.start) BETWEEN DATE(p.started_on) AND DATE(p.ended_on)
        JOIN `{PROJECT}.servicetitan.technician` AS t ON nja.technician_id = t.id
        WHERE nja.active = TRUE
          AND nja._fivetran_deleted = FALSE
          AND nja.start BETWEEN '{start_date}' AND '{end_date}'
          AND t.name NOT LIKE '%Sales%'
          AND t.name NOT IN ('Propane Subs', 'Maybruck')
          AND LOWER(nja.name) NOT LIKE '%off%'
          AND LOWER(nja.name) NOT LIKE '%pto%'
          AND LOWER(nja.name) NOT LIKE '%vacation%'
          AND LOWER(nja.name) NOT LIKE '%sick%'
          AND LOWER(nja.name) NOT LIKE '%funeral%'
          AND LOWER(nja.name) NOT LIKE '%injured%'
          AND LOWER(nja.name) NOT LIKE '%jury%'
          AND LOWER(nja.name) NOT LIKE '%not in%'
          AND LOWER(nja.name) NOT LIKE '%no mas%'
          AND LOWER(nja.name) NOT LIKE '%out%'
          AND LOWER(nja.name) NOT LIKE '%no schedule%'
        GROUP BY t.id, t.name
        ORDER BY total_hours DESC
    """)
    if not nonjob_detail.empty:
        nj_display = nonjob_detail.copy()
        nj_display.columns = ["Employee", "Shop Time", "Travel", "Meetings",
                               "Training", "Other", "Total Hrs", "Cost"]
        nj_display["Cost"] = nj_display["Cost"].astype(int)
        st.download_button(
            "Export Non-Job Time CSV ↓",
            nj_display.to_csv(index=False),
            file_name="nonjob_time_by_employee.csv",
            mime="text/csv",
        )
        st.dataframe(nj_display, width="stretch", hide_index=True, column_config={
            "Shop Time": st.column_config.NumberColumn(format="%.1f"),
            "Travel": st.column_config.NumberColumn(format="%.1f"),
            "Meetings": st.column_config.NumberColumn(format="%.1f"),
            "Training": st.column_config.NumberColumn(format="%.1f"),
            "Other": st.column_config.NumberColumn(format="%.1f"),
            "Total Hrs": st.column_config.NumberColumn(format="%.1f"),
            "Cost": st.column_config.NumberColumn(format="$%d"),
        })

# ─────────────────────────────────────────────
# TECHNICIANS
# ─────────────────────────────────────────────
elif page == "Technicians":
    st.title("Technician Performance")
    st.markdown("")

    bu_options = run_query(f"""
        SELECT DISTINCT j.business_unit_id,
               COALESCE(bu.name, CAST(j.business_unit_id AS STRING)) AS bu_name
        FROM `{PROJECT}.servicetitan.job` AS j
        LEFT JOIN `{PROJECT}.servicetitan.business_unit` AS bu ON j.business_unit_id = bu.id
        WHERE j._fivetran_deleted = FALSE
          AND j.job_status = 'Completed'
          AND j.completed_on BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY bu_name
    """)
    bu_map      = dict(zip(bu_options["bu_name"], bu_options["business_unit_id"]))
    dept_filter = st.selectbox("Department", ["All Departments"] + list(bu_map.keys()))
    dept_clause = f"AND j.business_unit_id = {bu_map[dept_filter]}" if dept_filter != "All Departments" else ""

    tech_data = run_query(f"""
        WITH completed_jobs AS (
            SELECT
                j.id AS job_id,
                j.completed_on,
                j.business_unit_id,
                COALESCE(fin.gross_profit, 0) AS gross_profit
            FROM `{PROJECT}.servicetitan.job` AS j
            LEFT JOIN (
                SELECT
                    i.job_id,
                    SUM(ii.total - COALESCE(ii.total_cost, 0)) AS gross_profit
                FROM `{PROJECT}.servicetitan.invoice` AS i
                JOIN `{PROJECT}.servicetitan.invoice_item` AS ii ON i.id = ii.invoice_id
                WHERE i._fivetran_deleted = FALSE
                  AND i.active = TRUE
                  AND ii._fivetran_deleted = FALSE
                  AND ii.active = TRUE
                GROUP BY i.job_id
            ) AS fin ON j.id = fin.job_id
            WHERE j._fivetran_deleted = FALSE
              AND j.job_status = 'Completed'
              AND j.completed_on BETWEEN '{start_date}' AND '{end_date}'
              {dept_clause}
        ),
        tech_job_time AS (
            SELECT
                ts.job_id,
                ts.technician_id,
                t.name AS technician_name,
                SUM(TIMESTAMP_DIFF(ts.done_on, ts.arrived_on, MINUTE) / 60.0) AS on_site_hours,
                SUM(TIMESTAMP_DIFF(ts.arrived_on, ts.dispatched_on, MINUTE) / 60.0) AS drive_hours,
                SUM(TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS worked_hours,
                SUM(
                    p.burden_rate * TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0
                ) AS labor_cost
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN completed_jobs AS j ON ts.job_id = j.job_id
            JOIN `{PROJECT}.servicetitan.payroll` AS p
                ON ts.technician_id = p.employee_id
                AND DATE(ts.dispatched_on) BETWEEN DATE(p.started_on) AND DATE(p.ended_on)
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
              {dept_clause}
            GROUP BY ts.job_id, ts.technician_id, t.name
        ),
        job_allocation AS (
            SELECT
                job_id,
                SUM(worked_hours) AS total_worked_hours
            FROM tech_job_time
            GROUP BY job_id
        ),
        tech_job_gp AS (
            SELECT
                tjt.technician_name,
                tjt.technician_id,
                tjt.job_id,
                CASE
                    WHEN ja.total_worked_hours > 0 THEN
                        j.gross_profit * tjt.worked_hours / ja.total_worked_hours
                    ELSE
                        0
                END AS attributed_gp_no_labor,
                tjt.labor_cost,
                tjt.on_site_hours,
                tjt.drive_hours
            FROM tech_job_time AS tjt
            JOIN completed_jobs AS j ON tjt.job_id = j.job_id
            JOIN job_allocation AS ja ON tjt.job_id = ja.job_id
        ),
        tech_rollup AS (
            SELECT
                technician_name,
                technician_id,
                COUNT(DISTINCT job_id) AS jobs,
                SUM(attributed_gp_no_labor - labor_cost) AS total_gp,
                SUM(on_site_hours) AS on_site_hours,
                SUM(drive_hours) AS drive_hours
            FROM tech_job_gp
            GROUP BY technician_name, technician_id
        ),
        unassigned_jobs AS (
            SELECT
                'Unassigned / Missing Job Time' AS technician_name,
                CAST(NULL AS INT64) AS technician_id,
                COUNT(*) AS jobs,
                SUM(j.gross_profit) AS total_gp,
                0.0 AS on_site_hours,
                0.0 AS drive_hours
            FROM completed_jobs AS j
            LEFT JOIN job_allocation AS ja ON j.job_id = ja.job_id
            WHERE ja.job_id IS NULL
               OR COALESCE(ja.total_worked_hours, 0) = 0
        ),
        dept_tech_hours AS (
            SELECT technician_id, SUM(worked_hours) AS dept_hours
            FROM tech_job_time
            GROUP BY technician_id
        ),
        all_tech_hours AS (
            SELECT
                ts.technician_id,
                SUM(TIMESTAMP_DIFF(ts.done_on, ts.dispatched_on, MINUTE) / 60.0) AS total_hours
            FROM `{PROJECT}.servicetitan.timesheet` AS ts
            JOIN `{PROJECT}.servicetitan.job` AS aj
                ON ts.job_id = aj.id
                AND aj._fivetran_deleted = FALSE
                AND aj.job_status = 'Completed'
                AND aj.completed_on BETWEEN '{start_date}' AND '{end_date}'
            JOIN `{PROJECT}.servicetitan.technician` AS t ON ts.technician_id = t.id
            WHERE ts._fivetran_deleted = FALSE
              AND ts.active = TRUE
              AND ts.dispatched_on IS NOT NULL
              AND ts.arrived_on IS NOT NULL
              AND ts.done_on IS NOT NULL
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
              AND ts.technician_id IN (SELECT technician_id FROM dept_tech_hours)
            GROUP BY ts.technician_id
        ),
        non_job AS (
            SELECT
                nja.technician_id,
                SUM(
                    (
                        SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(0)] AS FLOAT64) +
                        SAFE_CAST(SPLIT(nja.duration, ':')[OFFSET(1)] AS FLOAT64) / 60.0
                    )
                    * dth.dept_hours / ath.total_hours
                ) AS non_job_hours
            FROM `{PROJECT}.servicetitan.non_job_appointment` AS nja
            JOIN dept_tech_hours AS dth ON nja.technician_id = dth.technician_id
            JOIN all_tech_hours AS ath ON nja.technician_id = ath.technician_id
            JOIN `{PROJECT}.servicetitan.technician` AS t ON nja.technician_id = t.id
            WHERE nja.active = TRUE
              AND nja._fivetran_deleted = FALSE
              AND nja.start BETWEEN '{start_date}' AND '{end_date}'
              AND t.name NOT LIKE '%Sales%'
              AND t.name NOT IN ('Propane Subs', 'Maybruck')
              AND LOWER(nja.name) NOT LIKE '%off%'
              AND LOWER(nja.name) NOT LIKE '%pto%'
              AND LOWER(nja.name) NOT LIKE '%vacation%'
              AND LOWER(nja.name) NOT LIKE '%sick%'
              AND LOWER(nja.name) NOT LIKE '%funeral%'
              AND LOWER(nja.name) NOT LIKE '%injured%'
              AND LOWER(nja.name) NOT LIKE '%jury%'
              AND LOWER(nja.name) NOT LIKE '%not in%'
              AND LOWER(nja.name) NOT LIKE '%no mas%'
              AND LOWER(nja.name) NOT LIKE '%out%'
              AND LOWER(nja.name) NOT LIKE '%no schedule%'
            GROUP BY nja.technician_id
        ),
        final_rollup AS (
            SELECT
                technician_name,
                technician_id,
                jobs,
                total_gp,
                on_site_hours,
                drive_hours
            FROM tech_rollup
            UNION ALL
            SELECT
                technician_name,
                technician_id,
                jobs,
                total_gp,
                on_site_hours,
                drive_hours
            FROM unassigned_jobs
            WHERE jobs > 0
        )
        SELECT
            fr.technician_name,
            fr.jobs,
            fr.total_gp,
            fr.on_site_hours,
            fr.drive_hours,
            COALESCE(nj.non_job_hours, 0) AS non_job_hours,
            fr.on_site_hours + fr.drive_hours + COALESCE(nj.non_job_hours, 0) AS total_hours,
            COALESCE(SAFE_DIVIDE(fr.total_gp, fr.on_site_hours), 0) AS gp_per_job_hr,
            COALESCE(
                SAFE_DIVIDE(
                    fr.total_gp,
                    fr.on_site_hours + fr.drive_hours + COALESCE(nj.non_job_hours, 0)
                ),
                0
            ) AS gp_per_total_hr
        FROM final_rollup AS fr
        LEFT JOIN non_job AS nj ON fr.technician_id = nj.technician_id
        WHERE fr.jobs > 0
        ORDER BY gp_per_job_hr DESC, fr.total_gp DESC
    """)

    if not tech_data.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Avg GP / Job Hr",   f"${tech_data['gp_per_job_hr'].mean():,.0f}")
        c2.metric("Avg GP / Total Hr", f"${tech_data['gp_per_total_hr'].mean():,.0f}")
        c3.metric("Technicians",       f"{len(tech_data)}")

        st.markdown("")
        st.subheader("Technician Leaderboard")
        display = tech_data[["technician_name", "jobs", "total_gp",
                             "on_site_hours", "drive_hours", "non_job_hours",
                             "total_hours", "gp_per_job_hr", "gp_per_total_hr"]].copy()
        display.columns = ["Technician", "Jobs", "Gross Profit",
                           "On-Site Hrs", "Drive Hrs", "Non-Job Hrs",
                           "Total Hrs", "GP / Job Hr", "GP / Total Hr"]
        display.index = range(1, len(display) + 1)
        display.index.name = "Rank"
        display["Gross Profit"] = display["Gross Profit"].round(0).astype(int)
        display["On-Site Hrs"] = display["On-Site Hrs"].round(1)
        display["Drive Hrs"] = display["Drive Hrs"].round(1)
        display["Non-Job Hrs"] = display["Non-Job Hrs"].round(1)
        display["Total Hrs"] = display["Total Hrs"].round(1)
        display["GP / Job Hr"] = display["GP / Job Hr"].round(0).astype(int)
        display["GP / Total Hr"] = display["GP / Total Hr"].round(0).astype(int)
        st.dataframe(display, width="stretch", column_config={
            "Gross Profit": st.column_config.NumberColumn(format="$%d"),
            "On-Site Hrs": st.column_config.NumberColumn(format="%.1f"),
            "Drive Hrs": st.column_config.NumberColumn(format="%.1f"),
            "Non-Job Hrs": st.column_config.NumberColumn(format="%.1f"),
            "Total Hrs": st.column_config.NumberColumn(format="%.1f"),
            "GP / Job Hr": st.column_config.NumberColumn(format="$%d"),
            "GP / Total Hr": st.column_config.NumberColumn(format="$%d"),
        })
    else:
        st.info("No data for the selected range.")

# ─────────────────────────────────────────────
# CALLS
# ─────────────────────────────────────────────
elif page == "Calls":
    st.title("Calls & Booking Rate")
    st.markdown("")

    calls_kpi = run_query(f"""
        SELECT
            COUNT(*)                                                    AS total_inbound,
            COUNTIF(lead_call_call_type = 'Booked')                    AS booked,
            COUNTIF(lead_call_call_type = 'Unbooked')                  AS unbooked,
            COUNTIF(lead_call_call_type = 'Excused')                   AS excused,
            COUNTIF(lead_call_call_type = 'Abandoned')                 AS abandoned,
            COUNTIF(lead_call_call_type = 'NotLead')                   AS not_lead,
            SAFE_DIVIDE(
                COUNTIF(lead_call_call_type = 'Booked'),
                COUNTIF(lead_call_call_type IN ('Booked', 'Unbooked'))
            )                                                          AS booking_rate
        FROM `{PROJECT}.servicetitan.call`
        WHERE _fivetran_deleted = FALSE
          AND lead_call_direction = 'Inbound'
          AND lead_call_created_on BETWEEN '{start_date}' AND '{end_date}'
    """)

    total_inbound = int(calls_kpi["total_inbound"].iloc[0] or 0)
    booked        = int(calls_kpi["booked"].iloc[0] or 0)
    unbooked      = int(calls_kpi["unbooked"].iloc[0] or 0)
    excused       = int(calls_kpi["excused"].iloc[0] or 0)
    abandoned     = int(calls_kpi["abandoned"].iloc[0] or 0)
    not_lead      = int(calls_kpi["not_lead"].iloc[0] or 0)
    booking_rate  = float(calls_kpi["booking_rate"].iloc[0] or 0)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Inbound Calls", f"{total_inbound:,}")
    c2.metric("Booked",        f"{booked:,}")
    c3.metric("Unbooked",      f"{unbooked:,}")
    c4.metric("Excused",       f"{excused:,}")
    c5.metric("Abandoned",     f"{abandoned:,}")
    c6.metric("Booking Rate",  f"{booking_rate:.1%}")

    st.markdown("")
    st.subheader("Booking Rate Over Time")
    br_time = run_query(f"""
        SELECT
            DATE_TRUNC(DATE(lead_call_created_on), WEEK(MONDAY)) AS week_start,
            COUNT(*)                                              AS inbound,
            COUNTIF(lead_call_call_type = 'Booked')               AS booked,
            COUNTIF(lead_call_call_type = 'Unbooked')             AS unbooked,
            COUNTIF(lead_call_call_type = 'Excused')              AS excused,
            SAFE_DIVIDE(
                COUNTIF(lead_call_call_type = 'Booked'),
                COUNTIF(lead_call_call_type IN ('Booked', 'Unbooked'))
            )                                                     AS booking_rate
        FROM `{PROJECT}.servicetitan.call`
        WHERE _fivetran_deleted = FALSE
          AND lead_call_direction = 'Inbound'
          AND lead_call_created_on BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY week_start
        ORDER BY week_start
    """)
    if not br_time.empty:
        br_time["week_start"] = pd.to_datetime(br_time["week_start"])
        br_chart = (
            alt.Chart(br_time)
            .mark_line(point=True)
            .encode(
                x=alt.X("week_start:T", title="Week Starting", axis=alt.Axis(format="%m/%d/%Y", labelAngle=-25)),
                y=alt.Y("booking_rate:Q", title="Booking Rate", axis=alt.Axis(format=".0%")),
                tooltip=[
                    alt.Tooltip("week_start:T", title="Week Starting", format="%m/%d/%Y"),
                    alt.Tooltip("booking_rate:Q", title="Booking Rate", format=".1%"),
                    alt.Tooltip("booked:Q", title="Booked", format=","),
                    alt.Tooltip("inbound:Q", title="Inbound Calls", format=","),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(br_chart, use_container_width=True)
    else:
        st.info("No data for the selected range.")

    st.markdown("")
    st.subheader("Agent Performance")
    agents = run_query(f"""
        SELECT
            lead_call_agent_name                                       AS agent,
            COUNT(*)                                                   AS total_calls,
            COUNTIF(lead_call_call_type = 'Booked')                    AS booked,
            COUNTIF(lead_call_call_type = 'Unbooked')                  AS unbooked,
            COUNTIF(lead_call_call_type = 'Excused')                   AS excused,
            COUNTIF(lead_call_call_type = 'Abandoned')                 AS abandoned,
            SAFE_DIVIDE(
                COUNTIF(lead_call_call_type = 'Booked'),
                COUNTIF(lead_call_call_type IN ('Booked', 'Unbooked'))
            )                                                          AS booking_rate
        FROM `{PROJECT}.servicetitan.call`
        WHERE _fivetran_deleted = FALSE
          AND lead_call_direction = 'Inbound'
          AND lead_call_agent_name IS NOT NULL
          AND lead_call_created_on BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY agent
        HAVING COUNT(*) >= 5
        ORDER BY booking_rate DESC
    """)
    if not agents.empty:
        display_agents = agents.copy()
        display_agents.columns = ["Agent", "Total Calls", "Booked", "Unbooked",
                                  "Excused", "Abandoned", "Booking Rate"]
        display_agents["Booking Rate"] = (display_agents["Booking Rate"] * 100).round(1)
        display_agents.index = range(1, len(display_agents) + 1)
        display_agents.index.name = "Rank"
        st.dataframe(display_agents, width="stretch", column_config={
            "Booking Rate": st.column_config.NumberColumn(format="%.1f%%"),
        })
    else:
        st.info("No agent data for the selected range.")

    st.markdown("")
    st.subheader("Top Campaigns")
    campaigns = run_query(f"""
        SELECT
            COALESCE(c.name, 'Unknown') AS campaign,
            COUNT(*)                                                   AS calls,
            COUNTIF(cl.lead_call_call_type = 'Booked')                 AS booked,
            SAFE_DIVIDE(
                COUNTIF(cl.lead_call_call_type = 'Booked'),
                COUNTIF(cl.lead_call_call_type IN ('Booked', 'Unbooked'))
            )                                                          AS booking_rate
        FROM `{PROJECT}.servicetitan.call` AS cl
        LEFT JOIN `{PROJECT}.servicetitan.campaign` AS c ON cl.campaign_id = c.id
        WHERE cl._fivetran_deleted = FALSE
          AND cl.lead_call_direction = 'Inbound'
          AND cl.lead_call_created_on BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY campaign
        HAVING COUNT(*) >= 3
        ORDER BY calls DESC
        LIMIT 15
    """)
    if not campaigns.empty:
        display_campaigns = campaigns.copy()
        display_campaigns.columns = ["Campaign", "Calls", "Booked", "Booking Rate"]
        display_campaigns["Booking Rate"] = (display_campaigns["Booking Rate"] * 100).round(1)
        st.dataframe(display_campaigns, width="stretch", hide_index=True, column_config={
            "Booking Rate": st.column_config.NumberColumn(format="%.1f%%"),
        })
