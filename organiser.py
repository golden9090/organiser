import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta, time
import pytz
from streamlit_calendar import calendar

# ---------------------------------------------------------
# 1. PAGE CONFIG & MODERN STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="My Study Time | Academic Time Logger",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom sleek UI styling
st.markdown(
    """
<style>
    .reportview-container { background: #f8f9fa; }
    .big-font { font-size:24px !important; font-weight: 600; }
    .metric-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #3B82F6;
    }
    div[data-testid="stMetric"] {
        background-color: rgba(150, 150, 150, 0.15);
        padding: 10px;
        border-radius: 8px;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 2. SUPABASE INITIALIZATION & AUTH
# ---------------------------------------------------------
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# Handle OAuth Authentication
if not st.user.is_logged_in:
    st.title("My Study Time")
    st.info("Please sign in with your Google account to access your private study logs.")
    st.button("Log in with Google", on_click=st.login, type="primary")
    st.stop()

# Get secure, unique user ID to isolate data
USER_ID = st.user.get("sub", st.user.get("email", "unknown_user"))
USER_EMAIL = st.user.get("email", "Student")

# Sidebar User Profile & Logout
with st.sidebar:
    st.write(f"👤 **{USER_EMAIL}**")
    st.button("Log Out", on_click=st.logout, use_container_width=True)
    st.divider()

# ---------------------------------------------------------
# 3. HELPER FUNCTIONS & TIME MATH (AEST)
# ---------------------------------------------------------
AEST = pytz.timezone('Australia/Brisbane')  # AEST (UTC+10)

def get_aest_now():
    return datetime.now(AEST)

def calc_duration_mins(start_t: time, end_t: time) -> int:
    if not start_t or not end_t:
        return 0
    dt_start = datetime.combine(date.today(), start_t)
    dt_end = datetime.combine(date.today(), end_t)
    # Handle cross-midnight logs (e.g., 23:44 -> 00:44)
    if dt_end < dt_start:
        dt_end += timedelta(days=1)
    return int((dt_end - dt_start).total_seconds() / 60)

def format_mins(minutes: int) -> str:
    if minutes is None or pd.isna(minutes):
        return "-"
    abs_m = abs(int(minutes))
    h, m = divmod(abs_m, 60)
    sign = "-" if minutes < 0 else ""
    return f"{sign}{h}h {m}m"

# ---------------------------------------------------------
# 4. DATABASE QUERIES
# ---------------------------------------------------------
def get_trimesters():
    res = supabase.table("trimesters").select("name").eq("user_id", USER_ID).order("created_at").execute()
    return [r["name"] for r in res.data] if res.data else []

def get_courses(trimester_name):
    res = supabase.table("courses").select("*").eq("user_id", USER_ID).eq("trimester_name", trimester_name).execute()
    return res.data if res.data else []

def get_logs(trimester_name):
    res = supabase.table("time_logs").select("*").eq("user_id", USER_ID).eq("trimester_name", trimester_name).order("date_logged", desc=True).execute()
    return res.data if res.data else []

# ---------------------------------------------------------
# 5. MASTER SETTINGS (SIDEBAR)
# ---------------------------------------------------------
with st.sidebar:
  st.header("Master Settings")

  # Manage Trimesters
  with st.expander("Manage Trimesters"):
    new_tri = st.text_input("New Trimester (e.g., Tri 1 2026)")
    if st.button("Add Trimester", use_container_width=True) and new_tri:
      try:
        supabase.table("trimesters").insert(
            {"user_id": USER_ID, "name": new_tri.strip()}
        ).execute()
        st.success("Trimester added!")
        st.rerun()
      except Exception as e:
        st.error("Trimester already exists or error occurred.")

    trimesters = get_trimesters()
    if trimesters:
      st.divider()
      tri_to_del = st.selectbox("Select Trimester to Delete", trimesters)
      if st.button(
          f"🗑️ Delete {tri_to_del}", type="primary", use_container_width=True
      ):
        supabase.table("trimesters").delete().eq("user_id", USER_ID).eq(
            "name", tri_to_del
        ).execute()
        st.warning(f"Deleted {tri_to_del}!")
        st.rerun()

  trimesters = get_trimesters()
  if not trimesters:
    st.warning("⚠️ Create a trimester above to get started!")
    st.stop()

  selected_tri = st.selectbox("Active Trimester", trimesters)

  # Manage Courses
  with st.expander("Manage Courses"):
    new_code = st.text_input("Course Code (e.g., 1001MSC)")
    new_color = st.color_picker("Course Badge Color", "#3B82F6")
    if st.button("Add Course", use_container_width=True) and new_code:
      try:
        supabase.table("courses").insert({
            "user_id": USER_ID,
            "trimester_name": selected_tri,
            "course_code": new_code.upper().strip(),
            "color": new_color,
        }).execute()
        st.success("Course added!")
        st.rerun()
      except Exception as e:
        st.error("Course already exists.")

    courses_data = get_courses(selected_tri)
    if courses_data:
      st.divider()
      course_codes_list = [c["course_code"] for c in courses_data]
      course_to_del = st.selectbox("Select Course to Delete", course_codes_list)
      if st.button(f"Delete {course_to_del}", use_container_width=True):
        supabase.table("courses").delete().eq("user_id", USER_ID).eq(
            "trimester_name", selected_tri
        ).eq("course_code", course_to_del).execute()
        st.warning(f"Deleted {course_to_del}!")
        st.rerun()

courses_data = get_courses(selected_tri)
if not courses_data:
  st.warning(
      "⚠️ Please add at least one course in the sidebar settings for this"
      " trimester!"
  )
  st.stop()

course_codes = [c["course_code"] for c in courses_data]
color_map = {c["course_code"]: c["color"] for c in courses_data}

# ---------------------------------------------------------
# 6. MAIN INTERFACE TABS
# ---------------------------------------------------------
tab_logging, tab_analytics = st.tabs(["Time Logging & Calendar", "Analytics & Reports"])

# =========================================================
# TAB 1: TIME LOGGING & CALENDAR PREVIEW
# =========================================================
with tab_logging:
    st.subheader(f"Log Study Session — {selected_tri}")
    
    # -----------------------------------------------------
    # Input Section (Form removed for instant auto-calculation)
    # -----------------------------------------------------
    with st.container(border=True): # Optional: adds a nice border since we removed the form
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            log_date = st.date_input("Date (AEST)", value=get_aest_now().date())
        with col2:
            course = st.selectbox("Course*", course_codes)
        with col3:
            lesson_num = st.number_input("Lesson Number (1-12)*", min_value=1, max_value=12, value=1, step=1)
            
        details = st.text_input("Details (Lecture recordings, worksheets, revision, etc.)")
        
        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            p_start = st.time_input("Planned Start (Optional)", value=None)
        with c2:
            p_end = st.time_input("Planned End (Optional)", value=None)
        with c3:
            default_now = get_aest_now().time().replace(second=0, microsecond=0)
            a_start = st.time_input("Actual Start*", value=default_now)
        with c4:
            default_later = (get_aest_now() + timedelta(hours=1)).time().replace(second=0, microsecond=0)
            a_end = st.time_input("Actual End*", value=default_later)
            
        # Autocalculate values instantly on change
        p_dur = calc_duration_mins(p_start, p_end) if (p_start and p_end) else None
        a_dur = calc_duration_mins(a_start, a_end)
        var_mins = (a_dur - p_dur) if p_dur is not None else None
        
        # Display instant calculated metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Planned Duration", format_mins(p_dur) if p_dur else "Not Set")
        m2.metric("True Duration", format_mins(a_dur))
        m3.metric("Variation from Plan", format_mins(var_mins) if var_mins is not None else "N/A", 
                  delta=f"{var_mins} min" if var_mins is not None else None, delta_color="inverse")
        
        st.write("") # Spacer
        
        # Swapped to a standard button
        submitted = st.button("Log Session", type="primary", use_container_width=True)
        if submitted:
            log_entry = {
                "user_id": USER_ID,
                "trimester_name": selected_tri,
                "course_code": course,
                "lesson_num": lesson_num,
                "details": details,
                "date_logged": str(log_date),
                "planned_start": str(p_start) if p_start else None,
                "planned_end": str(p_end) if p_end else None,
                "planned_duration_mins": p_dur,
                "actual_start": str(a_start),
                "actual_end": str(a_end),
                "actual_duration_mins": a_dur,
                "variation_mins": var_mins
            }
            supabase.table("time_logs").insert(log_entry).execute()
            st.success("✅ Study time logged successfully!")
            st.rerun() # This will automatically clear the inputs back to their defaults

    st.divider()
    
    # -----------------------------------------------------
    # Calendar Preview (Past 7 Days)
    # -----------------------------------------------------
    st.subheader("7-Day Activity Calendar Preview")
    st.caption("Click any event on the interactive calendar below to view details or delete/edit.")
    
    all_logs = get_logs(selected_tri)
    
    if all_logs:
        df_logs = pd.DataFrame(all_logs)
        df_logs["date_logged"] = pd.to_datetime(df_logs["date_logged"]).dt.date
        
        # Filter for past 7 days from today AEST
        today_date = get_aest_now().date()
        seven_days_ago = today_date - timedelta(days=7)
        recent_logs = df_logs[(df_logs["date_logged"] >= seven_days_ago) & (df_logs["date_logged"] <= today_date)]
        
        # Build events array for fullcalendar
        cal_events = []
        for idx, row in recent_logs.iterrows():
            # Handle overnight dates visually on calendar
            start_iso = f"{row['date_logged']}T{row['actual_start']}"
            end_date_str = str(row['date_logged'])
            if row['actual_end'] < row['actual_start']:
                end_date_str = str(row['date_logged'] + timedelta(days=1))
            end_iso = f"{end_date_str}T{row['actual_end']}"
            
            cal_events.append({
                "title": f"{row['course_code']} (L{row['lesson_num']})",
                "start": start_iso,
                "end": end_iso,
                "backgroundColor": color_map.get(row['course_code'], "#3B82F6"),
                "borderColor": color_map.get(row['course_code'], "#3B82F6"),
                "extendedProps": {
                    "id": row["id"],
                    "details": row.get("details", ""),
                    "duration": format_mins(row["actual_duration_mins"])
                }
            })
            
        cal_options = {
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "timeGridWeek,timeGridDay",
            },
            "initialView": "timeGridWeek",
            "slotMinTime": "00:00:00",
            "slotMaxTime": "23:59:59",
            "height": 600,  # <-- Added this to force the grid to expand
            "allDaySlot": False,
        }
        
        cal_output = calendar(
            events=cal_events, 
            options=cal_options, 
            custom_css="""
                .fc-timegrid-slot {
                    height: 2.0em !important; /* Default is 1.5em. Increase this to make rows even taller! */
                }
            """,
            key="study_calendar"
        )
        
        # Handle Event Click (Modal/Dialog for editing)
        if cal_output and "eventClick" in cal_output:
            clicked_event = cal_output["eventClick"]["event"]
            e_id = clicked_event["extendedProps"]["id"]
            
            @st.dialog("Edit / Delete Log Entry")
            def edit_dialog(log_id):
                target_log = next((l for l in all_logs if l["id"] == log_id), None)
                if target_log:
                    st.write(f"**Course:** {target_log['course_code']} | **Lesson:** {target_log['lesson_num']}")
                    st.write(f"**Duration:** {format_mins(target_log['actual_duration_mins'])}")
                    new_details = st.text_input("Details", value=target_log.get("details") or "")
                    
                    col_u, col_d = st.columns(2)
                    with col_u:
                        if st.button("Update Details", type="primary", use_container_width=True):
                            supabase.table("time_logs").update({"details": new_details}).eq("id", log_id).execute()
                            st.success("Updated!")
                            st.rerun()
                    with col_d:
                        if st.button("Delete Log", use_container_width=True):
                            supabase.table("time_logs").delete().eq("id", log_id).execute()
                            st.warning("Deleted!")
                            st.rerun()
            
            edit_dialog(e_id)
            
    else:
        st.info("No study logs recorded yet for this trimester.")

    st.divider()
    
    # -----------------------------------------------------
    # Raw Data Table (Interactive & Editable)
    # -----------------------------------------------------
    st.subheader("My Data Table")
    if all_logs:
      df_display = pd.DataFrame(all_logs)
      df_display["True Duration"] = df_display["actual_duration_mins"].apply(
          format_mins
      )
      df_display["Planned Duration"] = df_display[
          "planned_duration_mins"
      ].apply(format_mins)
      df_display["Variation"] = df_display["variation_mins"].apply(format_mins)

      # Filter Widgets
      fc1, fc2 = st.columns(2)
      with fc1:
        unique_dates = sorted(list(df_display["date_logged"].unique()), reverse=True)
        sel_dates = st.multiselect("Filter by Date", unique_dates, default=[])
      with fc2:
        unique_courses = sorted(list(df_display["course_code"].unique()))
        sel_courses = st.multiselect(
            "Filter by Course", unique_courses, default=[]
        )

      # Apply Filters
      if sel_dates:
        df_display = df_display[df_display["date_logged"].isin(sel_dates)]
      if sel_courses:
        df_display = df_display[df_display["course_code"].isin(sel_courses)]

      cols_show = [
          "date_logged",
          "course_code",
          "lesson_num",
          "details",
          "actual_start",
          "actual_end",
          "True Duration",
          "Planned Duration",
          "Variation",
      ]

      st.dataframe(
          df_display[cols_show].rename(
              columns={
                  "date_logged": "Date",
                  "course_code": "Course",
                  "lesson_num": "Lesson",
                  "details": "Details",
                  "actual_start": "Start",
                  "actual_end": "End",
              }
          ),
          use_container_width=True,
          hide_index=True,
      )
    else:
      st.write("No data available.")

# =========================================================
# TAB 2: ANALYTICS & STATS
# =========================================================
with tab_analytics:
    st.subheader(f"Trimester Performance — {selected_tri}")
    
    all_logs = get_logs(selected_tri)
    if not all_logs:
        st.info("Log some study sessions in Tab 1 to generate analytics!")
        st.stop()
        
    df = pd.DataFrame(all_logs)
    df["date_logged"] = pd.to_datetime(df["date_logged"]).dt.date
    
    # -----------------------------------------------------
    # Matrix: Lessons (Rows) x Courses (Columns)
    # -----------------------------------------------------
    st.markdown("### Time Matrix: Lessons 1 to 12")
    st.caption(
        "Total hours and minutes spent on each specific lesson by course."
    )

    matrix_rows = []

    # Rows for Lesson 1 to 12
    for l_num in range(1, 13):
      row_dict = {"Lesson": f"Lsn {l_num}"}
      tot_lsn_mins = 0

      for code in course_codes:
        l_mins = df[
            (df["course_code"] == code) & (df["lesson_num"] == l_num)
        ]["actual_duration_mins"].sum()
        row_dict[code] = format_mins(l_mins) if l_mins > 0 else "-"
        tot_lsn_mins += l_mins

      row_dict["Total"] = format_mins(tot_lsn_mins) if tot_lsn_mins > 0 else "-"
      matrix_rows.append(row_dict)

    # Row for Total per Course
    total_row = {"Lesson": "Total"}
    for code in course_codes:
      c_tot = df[df["course_code"] == code]["actual_duration_mins"].sum()
      total_row[code] = format_mins(c_tot) if c_tot > 0 else "-"
    total_row["Total"] = format_mins(df["actual_duration_mins"].sum())
    matrix_rows.append(total_row)

    # Row for Average per Lesson (Total course time / 12)
    avg_row = {"Lesson": "Avg / Lsn"}
    for code in course_codes:
      c_tot = df[df["course_code"] == code]["actual_duration_mins"].sum()
      avg_row[code] = format_mins(int(c_tot / 12)) if c_tot > 0 else "-"
    tot_all = df["actual_duration_mins"].sum()
    avg_row["Total"] = format_mins(int(tot_all / 12)) if tot_all > 0 else "-"
    matrix_rows.append(avg_row)

    df_matrix = pd.DataFrame(matrix_rows)
    st.dataframe(df_matrix, use_container_width=True, hide_index=True)    
    st.divider()
    
    # -----------------------------------------------------
    # Customizable Pie Charts (% Time Spent)
    # -----------------------------------------------------
    st.markdown("### Time Breakdown Customiser")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        time_horizon = st.selectbox("Select Time Horizon", [
            "Entire Trimester", "Past 7 Days", "Today", "Custom Date Range"
        ])
    with col_f2:
        breakdown_by = st.selectbox("Group Time By", [
            "By Lesson Number", "By Course Code", "By Course & Lesson Combo"
        ])
        
    # Apply Time Filtering
    today_dt = get_aest_now().date()
    df_filtered = df.copy()
    
    if time_horizon == "Past 7 Days":
        df_filtered = df_filtered[df_filtered["date_logged"] >= (today_dt - timedelta(days=7))]
    elif time_horizon == "Today":
        df_filtered = df_filtered[df_filtered["date_logged"] == today_dt]
    elif time_horizon == "Custom Date Range":
        d_range = st.date_input("Select Date Range", value=(today_dt - timedelta(days=14), today_dt))
        if len(d_range) == 2:
            df_filtered = df_filtered[(df_filtered["date_logged"] >= d_range[0]) & (df_filtered["date_logged"] <= d_range[1])]

    if df_filtered.empty:
        st.warning("No logs found for the selected time horizon.")
    else:
        if breakdown_by == "By Lesson Number":
            fig = px.pie(
                df_filtered, values="actual_duration_mins", names="lesson_num",
                title=f"Time Distribution by Lesson ({time_horizon})",
                hole=0.4
            )
            fig.update_traces(textinfo="percent+label")
        elif breakdown_by == "By Course Code":
            fig = px.pie(
                df_filtered, values="actual_duration_mins", names="course_code",
                title=f"Time Distribution by Course ({time_horizon})",
                color="course_code", color_discrete_map=color_map,
                hole=0.4
            )
            fig.update_traces(textinfo="percent+label")
        else:
            df_filtered["Combo"] = df_filtered["course_code"] + " - Lsn " + df_filtered["lesson_num"].astype(str)
            fig = px.sunburst(
                df_filtered, path=["course_code", "Combo"], values="actual_duration_mins",
                color="course_code", color_discrete_map=color_map,
                title=f"Sunburst Hierarchy: Course & Lesson Breakdown ({time_horizon})"
            )
            
        fig.update_layout(height=500, margin=dict(t=50, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
