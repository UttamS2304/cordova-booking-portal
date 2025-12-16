# pages/2_Salesperson.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from config.settings import SESSION_KEYS
from db.connection import get_supabase
from utils.auth import logout
from db.allocation import assign_rp, available_slots_summary

st.title("Salesperson Dashboard")

# -------------------------
# Access Control
# -------------------------
if not st.session_state.get(SESSION_KEYS["logged_in"]):
    st.warning("Please login first.")
    st.stop()

user_row = st.session_state.get(SESSION_KEYS["user_row"], {})
if (user_row.get("role") or "").lower() != "salesperson":
    st.error("You are not authorized to view this page.")
    st.stop()

salesperson_id = user_row["id"]
supabase = get_supabase()

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.subheader("Salesperson Controls")
    st.write(f"Logged in as: **{user_row.get('email')}**")
    if st.button("Logout"):
        logout()
        st.rerun()

tabs = st.tabs(["Home", "My Bookings", "New Booking", "Feedback"])

# -------------------------
# TAB 1: HOME
# -------------------------
with tabs[0]:
    st.subheader("Summary")

    today_str = str(date.today())

    res = (
        supabase.table("bookings")
        .select("id, status, date, session_type_id")
        .eq("salesperson_id", salesperson_id)
        .execute()
    )
    all_bookings = res.data or []

    def count_where(fn):
        return sum(1 for b in all_bookings if fn(b))

    today_bookings = count_where(lambda b: b.get("date") == today_str)
    pending = count_where(lambda b: b.get("status") == "Pending")
    approved = count_where(lambda b: b.get("status") == "Approved")
    completed = count_where(lambda b: b.get("status") == "Completed")
    rejected_cancelled = count_where(lambda b: b.get("status") in ["Rejected", "Cancelled"])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Today's Bookings", today_bookings)
    col2.metric("Upcoming/Approved", approved)
    col3.metric("Pending Approval", pending)
    col4.metric("Completed Sessions", completed)
    col5.metric("Rejected/Cancelled", rejected_cancelled)

    st.divider()
    st.subheader("Notifications (basic)")

    last10 = sorted(all_bookings, key=lambda x: x.get("date", ""), reverse=True)[:10]
    if not last10:
        st.info("No notifications yet.")
    else:
        for b in last10:
            st.write(f"• Booking **{b.get('id')[:6]}** is **{b.get('status')}** for **{b.get('date')}**")

# -------------------------
# TAB 2: MY BOOKINGS
# -------------------------
with tabs[1]:
    st.subheader("My Bookings")

    fcol1, fcol2, fcol3 = st.columns(3)

    with fcol1:
        filter_range = st.selectbox(
            "Date Filter",
            ["All", "Today", "Tomorrow", "This Week"],
            key="mybookings_date_filter"
        )

    with fcol2:
        filter_status = st.selectbox(
            "Status Filter",
            ["All", "Pending", "Approved", "Completed", "Rejected", "Cancelled"],
            key="mybookings_status_filter"
        )

    with fcol3:
        subject_filter_on = st.checkbox("Show Subject Filter", value=False, key="mybookings_subject_filter_toggle")

    subject_id_filter = None
    if subject_filter_on:
        subjects_res = (
            supabase.table("subjects")
            .select("id,name")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        subjects = subjects_res.data or []
        subject_names = ["All"] + [s["name"] for s in subjects]
        chosen_subject = st.selectbox("Subject", subject_names, key="mybookings_subject_filter_select")
        if chosen_subject != "All":
            subject_id_filter = next(s["id"] for s in subjects if s["name"] == chosen_subject)

    res = (
        supabase.table("bookings")
        .select("""
            id,
            date,
            status,
            topic,
            title_name,
            session_type_id,
            subject_id,
            slot_id,
            school_id,
            rp_id
        """)
        .eq("salesperson_id", salesperson_id)
        .order("date", desc=True)
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

    if subject_id_filter:
        filtered = [r for r in filtered if r.get("subject_id") == subject_id_filter]

    if not filtered:
        st.info("No bookings found for selected filters.")
        st.stop()

    df = pd.DataFrame(filtered)

    # Lookups
    subjects = supabase.table("subjects").select("id,name").execute().data or []
    schools = supabase.table("schools").select("id,name").execute().data or []
    rps = supabase.table("resource_persons").select("id,display_name").execute().data or []
    session_types = supabase.table("session_types").select("id,name").execute().data or []
    slots = supabase.table("slots").select("id,start_time,end_time").execute().data or []

    subject_map = {s["id"]: s["name"] for s in subjects}
    school_map = {s["id"]: s["name"] for s in schools}
    rp_map = {r["id"]: r["display_name"] for r in rps}
    st_map = {t["id"]: t["name"] for t in session_types}
    slot_map = {sl["id"]: f'{sl["start_time"]} - {sl["end_time"]}' for sl in slots}

    df["Subject"] = df["subject_id"].map(subject_map)
    df["School"] = df["school_id"].map(school_map)
    df["RP"] = df["rp_id"].map(rp_map)
    df["Session Type"] = df["session_type_id"].map(st_map)
    df["Slot"] = df["slot_id"].map(slot_map)

    show_cols = [
        "date", "Slot", "Subject", "School", "Session Type",
        "topic", "title_name", "RP", "status", "id"
    ]
    st.dataframe(df[show_cols], use_container_width=True)

# -------------------------
# TAB 3: NEW BOOKING
# -------------------------
with tabs[2]:
    st.subheader("New Booking")
    subtab = st.tabs(["Creative Kids", "Little Genius"])

    def booking_form(tab_name: str):
        prefix = tab_name.replace(" ", "_").lower()
        st.markdown(f"### {tab_name} Booking Form")

        subjects = supabase.table("subjects").select("id,name").eq("is_active", True).order("name").execute().data or []
        slots = supabase.table("slots").select("id,start_time,end_time,duration_minutes").eq("is_active", True).order("start_time").execute().data or []
        session_types = supabase.table("session_types").select("id,name,duration_minutes").eq("is_active", True).order("name").execute().data or []
        schools = supabase.table("schools").select("id,name,city").eq("is_active", True).order("name").execute().data or []

        subject_map = {s["name"]: s["id"] for s in subjects}
        slot_label_map = {f'{s["start_time"]} - {s["end_time"]}': s["id"] for s in slots}
        session_map = {s["name"]: s["id"] for s in session_types}

        school_names = ["Select School"] + [sc["name"] for sc in schools] + ["➕ Add New School"]
        school_choice = st.selectbox("School Name*", school_names, key=f"{prefix}_school")

        new_school_name = ""
        new_school_city = ""
        if school_choice == "➕ Add New School":
            new_school_name = st.text_input("New School Name*", key=f"{prefix}_new_school_name")
            new_school_city = st.text_input("City*", key=f"{prefix}_new_school_city")

        city = st.text_input("City*", value=new_school_city if new_school_city else "", key=f"{prefix}_city")

        booking_date = st.date_input("Date*", value=None, key=f"{prefix}_date")

        subject_name = st.selectbox("Subject*", ["Select Subject"] + list(subject_map.keys()), key=f"{prefix}_subject")
        session_name = st.selectbox("Session Type*", ["Select Type"] + list(session_map.keys()), key=f"{prefix}_session_type")

        if subject_name != "Select Subject" and booking_date and session_name != "Select Type":
            summary = available_slots_summary(
                subject_map[subject_name],
                str(booking_date),
                session_map[session_name]
            )
            df_sum = pd.DataFrame(summary)
            if not df_sum.empty:
                df_sum["Slot"] = df_sum.apply(lambda r: f'{r["start_time"]} - {r["end_time"]}', axis=1)
                df_sum = df_sum[["Slot", "remaining_parallel", "possible_rps"]]
                df_sum.columns = ["Slot", "Remaining Parallel Capacity", "Possible RPs Available"]
                st.info("Available slots for selected subject/date/type:")
                st.dataframe(df_sum, use_container_width=True)

        slot_label = st.selectbox("Slot*", ["Select Slot"] + list(slot_label_map.keys()), key=f"{prefix}_slot")

        class_name = st.text_input("Class*", placeholder="e.g., 1 / 2 / 3", key=f"{prefix}_class")
        grade_of_school = st.text_input("Grade of School*", placeholder="Primary / Secondary etc.", key=f"{prefix}_grade")
        curriculum = st.text_input("Curriculum*", placeholder="CBSE / ICSE / State etc.", key=f"{prefix}_curriculum")

        topic = st.text_input("Topic*", placeholder="Mandatory for all", key=f"{prefix}_topic")
        title_name = st.text_input("Title Name*", placeholder="Mandatory for all", key=f"{prefix}_title")
        notes = st.text_area("Notes (optional)", key=f"{prefix}_notes")

        if st.button(f"Submit {tab_name} Booking", use_container_width=True, key=f"{prefix}_submit"):
            if school_choice == "Select School":
                st.error("Please select or add a school."); return
            if school_choice == "➕ Add New School" and (not new_school_name or not city):
                st.error("Please enter new school name and city."); return
            if not booking_date:
                st.error("Please select date."); return
            if subject_name == "Select Subject":
                st.error("Please select subject."); return
            if session_name == "Select Type":
                st.error("Please select session type."); return
            if slot_label == "Select Slot":
                st.error("Please select slot."); return
            if not class_name or not grade_of_school or not curriculum:
                st.error("Class, grade, and curriculum are required."); return
            if not topic or not title_name:
                st.error("Topic and Title Name are mandatory."); return

            if school_choice == "➕ Add New School":
                sc_res = supabase.table("schools").insert({
                    "name": new_school_name,
                    "city": city,
                    "is_active": True
                }).execute()
                school_id = (sc_res.data or [None])[0]["id"]
            else:
                school_id = next(sc["id"] for sc in schools if sc["name"] == school_choice)

            subject_id = subject_map[subject_name]
            slot_id = slot_label_map[slot_label]
            session_type_id = session_map[session_name]

            rp_id = assign_rp(
                subject_id=subject_id,
                slot_id=slot_id,
                booking_date=str(booking_date),
                session_type_id=session_type_id,
                school_id=school_id
            )

            if not rp_id:
                st.error("No Resource Person available for this slot/subject. Try another slot.")
                return

            insert_res = supabase.table("bookings").insert({
                "school_id": school_id,
                "salesperson_id": salesperson_id,
                "subject_id": subject_id,
                "slot_id": slot_id,
                "session_type_id": session_type_id,
                "date": str(booking_date),
                "city": city,
                "class_name": class_name,
                "grade_of_school": grade_of_school,
                "curriculum": curriculum,
                "topic": topic,
                "title_name": title_name,
                "notes": notes,
                "rp_id": rp_id,
                "status": "Pending",
                "tab_type": tab_name
            }).execute()

            booking_row = (insert_res.data or [None])[0]
            st.success("Booking submitted successfully! Status: Pending Approval")
            st.write("Assigned RP ID:", rp_id)
            st.write("Booking ID:", booking_row["id"])

    with subtab[0]:
        booking_form("Creative Kids")

    with subtab[1]:
        booking_form("Little Genius")

# -------------------------
# TAB 4: FEEDBACK
# -------------------------
with tabs[3]:
    st.subheader("Submit Feedback (Completed Sessions)")

    completed_res = (
        supabase.table("bookings")
        .select("""
            id, date, status, topic, title_name,
            subject_id, slot_id, school_id, session_type_id, rp_id
        """)
        .eq("salesperson_id", salesperson_id)
        .eq("status", "Completed")
        .order("date", desc=True)
        .execute()
    )
    completed_rows = completed_res.data or []

    if not completed_rows:
        st.info("No completed sessions yet.")
        st.stop()

    fb_res = (
        supabase.table("feedback")
        .select("booking_id")
        .eq("salesperson_id", salesperson_id)
        .execute()
    )
    submitted_ids = {f["booking_id"] for f in (fb_res.data or [])}

    pending_feedback = [b for b in completed_rows if b["id"] not in submitted_ids]

    if not pending_feedback:
        st.success("All completed sessions already have feedback submitted ✅")
        st.stop()

    subjects = supabase.table("subjects").select("id,name").execute().data or []
    schools = supabase.table("schools").select("id,name,city").execute().data or []
    rps = supabase.table("resource_persons").select("id,display_name").execute().data or []
    session_types = supabase.table("session_types").select("id,name").execute().data or []
    slots = supabase.table("slots").select("id,start_time,end_time").execute().data or []

    subject_map = {s["id"]: s["name"] for s in subjects}
    school_map = {s["id"]: s["name"] for s in schools}
    rp_map = {r["id"]: r["display_name"] for r in rps}
    st_map = {t["id"]: t["name"] for t in session_types}
    slot_map = {sl["id"]: f'{sl["start_time"]} - {sl["end_time"]}' for sl in slots}

    booking_options = [
        f'{b["date"]} | {slot_map.get(b["slot_id"])} | {subject_map.get(b["subject_id"])} | {school_map.get(b["school_id"])} | {b["id"][:6]}'
        for b in pending_feedback
    ]
    selected_label = st.selectbox("Select completed booking", booking_options, key="fb_booking_select")
    selected_idx = booking_options.index(selected_label)
    selected_booking = pending_feedback[selected_idx]

    st.markdown("### Booking Summary")
    st.write("**School:**", school_map.get(selected_booking["school_id"]))
    st.write("**Subject:**", subject_map.get(selected_booking["subject_id"]))
    st.write("**Slot:**", slot_map.get(selected_booking["slot_id"]))
    st.write("**Session Type:**", st_map.get(selected_booking["session_type_id"]))
    st.write("**RP:**", rp_map.get(selected_booking["rp_id"]))
    st.write("**Topic:**", selected_booking.get("topic"))
    st.write("**Title Name:**", selected_booking.get("title_name"))

    st.divider()
    st.markdown("### Feedback Form")

    was_conducted = st.radio("Was the session conducted?", ["Yes", "No"], key="fb_conducted")
    teacher_response_rating = st.slider("How was the teacher response?", 1, 5, 4, key="fb_teacher_rating")
    engagement_rating = st.slider("How was the student engagement?", 1, 5, 4, key="fb_engagement_rating")
    school_feedback = st.text_area("Did school share any feedback?", key="fb_school_feedback")
    notes = st.text_area("Additional notes (optional)", key="fb_notes")

    if st.button("✅ Submit Feedback", use_container_width=True, key="fb_submit_btn"):
        supabase.table("feedback").insert({
            "booking_id": selected_booking["id"],
            "salesperson_id": salesperson_id,
            "was_conducted": was_conducted,
            "teacher_response_rating": teacher_response_rating,
            "engagement_rating": engagement_rating,
            "school_feedback": school_feedback,
            "notes": notes
        }).execute()

        st.success("Feedback submitted successfully ✅")
        st.rerun()
