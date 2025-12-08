# pages/4_RP.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from config.settings import SESSION_KEYS
from db.connection import get_supabase
from utils.auth import logout

st.set_page_config(page_title="RP | Cordova Booking Portal", layout="wide")
st.title("Resource Person Dashboard")

# -------------------------
# Access Control
# -------------------------
if not st.session_state.get(SESSION_KEYS["logged_in"]):
    st.warning("Please login first.")
    st.stop()

user_row = st.session_state.get(SESSION_KEYS["user_row"], {})
if user_row.get("role") != "rp":
    st.error("You are not authorized to view this page.")
    st.stop()

supabase = get_supabase()
rp_user_id = user_row["id"]

# -------------------------
# Find linked RP record
# -------------------------
rp_res = (
    supabase.table("resource_persons")
    .select("id, display_name, user_id")
    .eq("user_id", rp_user_id)
    .limit(1)
    .execute()
)
rp_row = (rp_res.data or [None])[0]

if not rp_row:
    st.error("Your RP profile is not linked yet. Please contact Admin.")
    st.stop()

rp_id = rp_row["id"]

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.subheader("RP Controls")
    st.write(f"Logged in as: **{rp_row.get('display_name')}**")
    if st.button("Logout"):
        logout()
        st.rerun()

tabs = st.tabs(["Home", "My Classes"])

# -------------------------
# LOOKUPS
# -------------------------
subjects = supabase.table("subjects").select("id,name").execute().data or []
schools = supabase.table("schools").select("id,name,city").execute().data or []
session_types = supabase.table("session_types").select("id,name").execute().data or []
slots = supabase.table("slots").select("id,start_time,end_time").execute().data or []

subject_map = {s["id"]: s["name"] for s in subjects}
school_map = {s["id"]: s["name"] for s in schools}
school_city_map = {s["id"]: s.get("city") for s in schools}
st_map = {t["id"]: t["name"] for t in session_types}
slot_map = {sl["id"]: f'{sl["start_time"]} - {sl["end_time"]}' for sl in slots}

# -------------------------
# TAB 1: HOME
# -------------------------
with tabs[0]:
    st.subheader("Summary")

    today_str = str(date.today())
    month_start = str(date.today().replace(day=1))

    res_all = (
        supabase.table("bookings")
        .select("id, date, status, session_type_id, subject_id")
        .eq("rp_id", rp_id)
        .execute()
    )
    all_classes = res_all.data or []

    def count_where(fn):
        return sum(1 for b in all_classes if fn(b))

    today_classes = count_where(lambda b: b.get("date") == today_str and b.get("status") in ["Approved", "Scheduled"])
    tomorrow_classes = count_where(lambda b: b.get("date") == str(date.today() + timedelta(days=1)) and b.get("status") in ["Approved", "Scheduled"])
    month_classes = count_where(lambda b: b.get("date") >= month_start)
    avrd_classes = count_where(lambda b: st_map.get(b.get("session_type_id")) == "AVRD")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's Classes", today_classes)
    c2.metric("Tomorrow's Classes", tomorrow_classes)
    c3.metric("Total Classes This Month", month_classes)
    c4.metric("Total AVRD This Month", avrd_classes)

# -------------------------
# TAB 2: MY CLASSES + Attendance
# -------------------------
with tabs[1]:
    st.subheader("My Assigned Classes")

    f1, f2, f3 = st.columns(3)

    with f1:
        filter_range = st.selectbox("Date Filter", ["Today", "Tomorrow", "This Week", "All"], key="rp_filter_range")

    with f2:
        filter_status = st.selectbox(
            "Status Filter",
            ["All", "Pending", "Approved", "Scheduled", "Completed", "Cancelled", "Rejected"],
            key="rp_filter_status"
        )

    with f3:
        filter_subject = st.selectbox(
            "Subject Filter",
            ["All"] + [s["name"] for s in subjects],
            key="rp_filter_subject"
        )

    res = (
        supabase.table("bookings")
        .select("""
            id, date, status, topic, title_name, notes,
            school_id, subject_id, slot_id, session_type_id, city,
            rp_attendance_status, rp_session_notes, rp_marked_at
        """)
        .eq("rp_id", rp_id)
        .order("date", desc=False)
        .execute()
    )
    rows = res.data or []

    def in_range(d):
        if filter_range == "All":
            return True
        if not d:
            return False
        dd = date.fromisoformat(d)
        if filter_range == "Today":
            return dd == date.today()
        if filter_range == "Tomorrow":
            return dd == date.today() + timedelta(days=1)
        if filter_range == "This Week":
            return date.today() <= dd <= date.today() + timedelta(days=7)
        return True

    filtered = [r for r in rows if in_range(r.get("date"))]

    if filter_status != "All":
        filtered = [r for r in filtered if r.get("status") == filter_status]

    if filter_subject != "All":
        sub_id = next(s["id"] for s in subjects if s["name"] == filter_subject)
        filtered = [r for r in filtered if r.get("subject_id") == sub_id]

    if not filtered:
        st.info("No classes found for selected filters.")
        st.stop()

    df = pd.DataFrame(filtered)

    df["Subject"] = df["subject_id"].map(subject_map)
    df["School"] = df["school_id"].map(school_map)
    df["School City"] = df["school_id"].map(school_city_map)
    df["Session Type"] = df["session_type_id"].map(st_map)
    df["Slot"] = df["slot_id"].map(slot_map)

    show_cols = [
        "date", "Slot", "Subject", "Session Type",
        "School", "School City",
        "topic", "title_name",
        "status", "rp_attendance_status", "rp_session_notes", "id"
    ]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True)

    st.divider()
    st.subheader("Mark Attendance & Submit Notes")

    # Select booking to update
    booking_options = [
        f'{r["date"]} | {slot_map.get(r["slot_id"])} | {subject_map.get(r["subject_id"])} | {school_map.get(r["school_id"])} | {r["id"][:6]}'
        for r in filtered
    ]
    selected_label = st.selectbox("Select class to update", booking_options, key="rp_booking_select")
    selected_idx = booking_options.index(selected_label)
    selected_booking = filtered[selected_idx]

    st.markdown("### Selected Class Details")
    st.json(selected_booking)

    attendance_status = st.selectbox(
        "Attendance Status",
        ["Completed", "Not Completed", "Postponed", "School Absent", "Network Issue"],
        index=0,
        key="rp_attendance_status_select"
    )

    session_notes = st.text_area(
        "Session Notes (Summary / Issues / Suggestions)",
        value=selected_booking.get("rp_session_notes") or "",
        key="rp_notes_area"
    )

    if st.button("✅ Save Attendance & Notes", use_container_width=True, key="rp_save_attendance"):
        try:
            supabase.table("bookings").update({
                "rp_attendance_status": attendance_status,
                "rp_session_notes": session_notes,
                "rp_marked_at": datetime.utcnow().isoformat(),
                # auto-mark booking completed if RP says Completed
                "status": "Completed" if attendance_status == "Completed" else selected_booking.get("status")
            }).eq("id", selected_booking["id"]).execute()

            st.success("Attendance & notes saved.")
            st.rerun()

        except Exception as e:
            st.error(
                "Update failed. Most likely your bookings table is missing columns.\n\n"
                "Please add these 3 columns in Supabase → bookings table:\n"
                "1) rp_attendance_status (text)\n"
                "2) rp_session_notes (text)\n"
                "3) rp_marked_at (timestamptz)\n\n"
                f"Error: {e}"
            )
