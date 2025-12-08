# pages/3_Admin.py
import streamlit as st
import pandas as pd
from datetime import date
from config.settings import SESSION_KEYS
from db.connection import get_supabase
from utils.auth import logout

st.set_page_config(page_title="Admin | Cordova Booking Portal", layout="wide")
st.title("Admin Dashboard")

# --- Access control: only admin can open ---
if not st.session_state.get(SESSION_KEYS["logged_in"]):
    st.warning("Please login first.")
    st.stop()

user_row = st.session_state.get(SESSION_KEYS["user_row"], {})
if user_row.get("role") != "admin":
    st.error("You are not authorized to view this page.")
    st.stop()

supabase = get_supabase()

# --- Sidebar ---
with st.sidebar:
    st.subheader("Admin Controls")
    st.write(f"Logged in as: **{user_row.get('email')}**")
    if st.button("Logout"):
        logout()
        st.rerun()

tabs = st.tabs([
    "Home (Coming Soon)",
    "User Approvals",
    "Bookings",
    "Feedback & Reports",
    "Teachers"
])
# ---------------------------
# TAB 1: ADMIN HOME DASHBOARD
# ---------------------------
with tabs[0]:
    st.subheader("Admin Home Dashboard")

    today_str = str(date.today())

    # --- Fetch today bookings ---
    today_res = (
        supabase.table("bookings")
        .select("""
            id, status, subject_id, rp_id, slot_id, session_type_id, school_id, date
        """)
        .eq("date", today_str)
        .execute()
    )
    today_rows = today_res.data or []

    # --- Fetch lookups ---
    subjects = supabase.table("subjects").select("id,name").execute().data or []
    rps = supabase.table("resource_persons").select("id,display_name").execute().data or []
    slots = supabase.table("slots").select("id,start_time,end_time").execute().data or []
    session_types = supabase.table("session_types").select("id,name").execute().data or []
    schools = supabase.table("schools").select("id,name").execute().data or []

    subject_map = {s["id"]: s["name"] for s in subjects}
    rp_map = {r["id"]: r["display_name"] for r in rps}
    slot_map = {sl["id"]: f'{sl["start_time"]} - {sl["end_time"]}' for sl in slots}
    st_map = {t["id"]: t["name"] for t in session_types}
    school_map = {sc["id"]: sc["name"] for sc in schools}

    # --- Summary cards ---
    total_today = len(today_rows)
    pending_today = sum(1 for b in today_rows if b.get("status") == "Pending")
    approved_today = sum(1 for b in today_rows if b.get("status") == "Approved")
    rejected_today = sum(1 for b in today_rows if b.get("status") == "Rejected")
    cancelled_today = sum(1 for b in today_rows if b.get("status") == "Cancelled")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Bookings Today", total_today)
    c2.metric("Approved", approved_today)
    c3.metric("Pending", pending_today)
    c4.metric("Rejected", rejected_today)
    c5.metric("Cancelled", cancelled_today)

    st.divider()

    # --- Subject-wise count ---
    st.markdown("### Subject-wise Booking Count (Today)")
    subj_counts = {}
    for b in today_rows:
        sid = b.get("subject_id")
        name = subject_map.get(sid, "Unknown")
        subj_counts[name] = subj_counts.get(name, 0) + 1

    df_subj = pd.DataFrame(
        [{"Subject": k, "Bookings": v} for k, v in subj_counts.items()]
    ).sort_values("Bookings", ascending=False)

    if df_subj.empty:
        st.info("No bookings today.")
    else:
        st.dataframe(df_subj, use_container_width=True)

    st.divider()

    # --- RP-wise load today ---
    st.markdown("### RP-wise Load Summary (Today)")
    rp_counts = {}
    for b in today_rows:
        rid = b.get("rp_id")
        name = rp_map.get(rid, "Unassigned")
        rp_counts[name] = rp_counts.get(name, 0) + 1

    df_rp = pd.DataFrame(
        [{"RP": k, "Classes Today": v} for k, v in rp_counts.items()]
    ).sort_values("Classes Today", ascending=False)

    if df_rp.empty:
        st.info("No RP load yet.")
    else:
        st.dataframe(df_rp, use_container_width=True)

    st.divider()

    # --- Today's absent teachers ---
    st.markdown("### Today's Absent Teachers")
    abs_res = (
        supabase.table("rp_unavailability")
        .select("rp_id, date, is_full_day, slot_id, session_type_id")
        .eq("date", today_str)
        .execute()
    )
    abs_rows = abs_res.data or []

    if not abs_rows:
        st.success("No absences today ✅")
    else:
        absent_view = []
        for a in abs_rows:
            absent_view.append({
                "RP": rp_map.get(a["rp_id"]),
                "Full Day": a.get("is_full_day"),
                "Slot": slot_map.get(a.get("slot_id")) if a.get("slot_id") else "-",
                "Session Type": st_map.get(a.get("session_type_id")) if a.get("session_type_id") else "-"
            })
        st.dataframe(pd.DataFrame(absent_view), use_container_width=True)

    st.divider()

    # --- Next 3 upcoming sessions (today onwards) ---
    st.markdown("### Next 3 Upcoming Sessions")
    upcoming_res = (
        supabase.table("bookings")
        .select("""
            id, date, status, subject_id, rp_id, slot_id, session_type_id, school_id, topic
        """)
        .gte("date", today_str)
        .in_("status", ["Approved", "Scheduled", "Pending"])
        .order("date", desc=False)
        .limit(3)
        .execute()
    )
    upcoming = upcoming_res.data or []

    if not upcoming:
        st.info("No upcoming sessions.")
    else:
        up_view = []
        for b in upcoming:
            up_view.append({
                "Date": b.get("date"),
                "Slot": slot_map.get(b.get("slot_id")),
                "Subject": subject_map.get(b.get("subject_id")),
                "Session Type": st_map.get(b.get("session_type_id")),
                "School": school_map.get(b.get("school_id")),
                "RP": rp_map.get(b.get("rp_id")),
                "Status": b.get("status"),
                "Topic": b.get("topic"),
            })
        st.dataframe(pd.DataFrame(up_view), use_container_width=True)


# ---------------------------
# TAB 2: USER APPROVALS
# ---------------------------
with tabs[1]:
    st.subheader("Pending User Approvals")

    res = (
        supabase.table("users")
        .select("id, name, email, role, is_active, created_at")
        .eq("is_active", False)
        .in_("role", ["salesperson", "rp"])
        .order("created_at", desc=True)
        .execute()
    )

    pending_users = res.data or []

    if not pending_users:
        st.success("No pending users right now.")
    else:
        df = pd.DataFrame(pending_users)

        df["role"] = df["role"].replace({
            "salesperson": "Salesperson",
            "rp": "Resource Person"
        })

        st.dataframe(df, use_container_width=True)

        st.divider()
        st.markdown("### Approve / Reject Users")

        options = [f"{u['email']} ({u['role']})" for u in pending_users]
        selected = st.selectbox("Select a pending user", options, key="pending_user_select")

        selected_user = pending_users[options.index(selected)]

        colA, colB = st.columns(2)

        with colA:
            if st.button("✅ Approve User", use_container_width=True, key="approve_user_btn"):
                supabase.table("users").update({
                    "is_active": True
                }).eq("id", selected_user["id"]).execute()

                st.success(f"Approved: {selected_user['email']}")
                st.rerun()

        with colB:
            if st.button("❌ Reject/Delete User", use_container_width=True, key="reject_user_btn"):
                supabase.table("users").delete().eq("id", selected_user["id"]).execute()

                st.warning(f"Deleted: {selected_user['email']}")
                st.rerun()

# ---------------------------
# TAB 3: BOOKINGS MANAGEMENT
# ---------------------------
with tabs[2]:
    st.subheader("All Bookings")

    # Lookup maps
    subjects = supabase.table("subjects").select("id,name").execute().data or []
    schools = supabase.table("schools").select("id,name,city").execute().data or []
    rps = supabase.table("resource_persons").select("id,display_name").execute().data or []
    session_types = supabase.table("session_types").select("id,name,duration_minutes").execute().data or []
    slots = supabase.table("slots").select("id,start_time,end_time,duration_minutes").execute().data or []
    salespersons = supabase.table("users").select("id,email,name").eq("role", "salesperson").execute().data or []

    subject_map = {s["id"]: s["name"] for s in subjects}
    school_map = {s["id"]: s["name"] for s in schools}
    school_city_map = {s["id"]: s.get("city") for s in schools}
    rp_map = {r["id"]: r["display_name"] for r in rps}
    st_map = {t["id"]: t["name"] for t in session_types}
    slot_map = {sl["id"]: f'{sl["start_time"]} - {sl["end_time"]}' for sl in slots}
    sp_map = {u["id"]: (u.get("name") or u.get("email")) for u in salespersons}

    # Filters
    f1, f2, f3, f4, f5 = st.columns(5)

    with f1:
        filter_date = st.date_input("Filter Date", value=None, key="admin_booking_date")

    with f2:
        filter_status = st.selectbox(
            "Status",
            ["All", "Pending", "Approved", "Rejected", "Cancelled", "Completed"],
            key="admin_booking_status"
        )

    with f3:
        filter_subject = st.selectbox(
            "Subject",
            ["All"] + [s["name"] for s in subjects],
            key="admin_booking_subject"
        )

    with f4:
        filter_rp = st.selectbox(
            "Resource Person",
            ["All"] + [r["display_name"] for r in rps],
            key="admin_booking_rp"
        )

    with f5:
        filter_salesperson = st.selectbox(
            "Salesperson",
            ["All"] + [sp_map[u["id"]] for u in salespersons],
            key="admin_booking_salesperson"
        )

    # Fetch bookings
    q = supabase.table("bookings").select("""
    id,
    date,
    status,
    topic,
    title_name,
    notes,
    city,
    class_name,
    grade_of_school,
    curriculum,
    tab_type,
    school_id,
    salesperson_id,
    subject_id,
    slot_id,
    session_type_id,
    rp_id,
    rp_attendance_status,
    rp_session_notes,
    rp_marked_at
""").order("date", desc=True)

    if filter_date:
        q = q.eq("date", str(filter_date))
    if filter_status != "All":
        q = q.eq("status", filter_status)
    if filter_subject != "All":
        sub_id = next(s["id"] for s in subjects if s["name"] == filter_subject)
        q = q.eq("subject_id", sub_id)
    if filter_rp != "All":
        rp_id = next(r["id"] for r in rps if r["display_name"] == filter_rp)
        q = q.eq("rp_id", rp_id)
    if filter_salesperson != "All":
        sp_id = next(k for k, v in sp_map.items() if v == filter_salesperson)
        q = q.eq("salesperson_id", sp_id)

    res = q.execute()
    rows = res.data or []

    if not rows:
        st.info("No bookings found for selected filters.")
        st.stop()

    df = pd.DataFrame(rows)

    # readable columns
    df["Subject"] = df["subject_id"].map(subject_map)
    df["School"] = df["school_id"].map(school_map)
    df["School City"] = df["school_id"].map(school_city_map)
    df["RP"] = df["rp_id"].map(rp_map)
    df["Session Type"] = df["session_type_id"].map(st_map)
    df["Slot"] = df["slot_id"].map(slot_map)
    df["Salesperson"] = df["salesperson_id"].map(sp_map)

    show_cols = [
    "date", "Slot", "Subject", "Session Type",
    "School", "School City", "class_name",
    "topic", "title_name", "RP",
    "status",
    "rp_attendance_status",
    "rp_session_notes",
    "rp_marked_at",
    "Salesperson", "tab_type", "id" 
    ]

    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True)

    st.divider()

    # Manage booking
    st.subheader("Approve / Reject / Cancel / Edit")

    booking_options = [
        f'{r["date"]} | {slot_map.get(r["slot_id"])} | {subject_map.get(r["subject_id"])} | {school_map.get(r["school_id"])} | {r["id"][:6]}'
        for r in rows
    ]

    selected_label = st.selectbox("Select a booking", booking_options, key="admin_booking_select")
    selected_idx = booking_options.index(selected_label)
    selected_booking = rows[selected_idx]

    st.markdown("### Booking Details")
    st.json(selected_booking)

    action_col1, action_col2, action_col3, action_col4 = st.columns(4)

    # Approve
    with action_col1:
        if st.button("✅ Approve Booking", use_container_width=True, key="admin_approve_btn"):
            if selected_booking["status"] != "Pending":
                st.warning("Only Pending bookings can be approved.")
            else:
                supabase.table("bookings").update({
                    "status": "Approved"
                }).eq("id", selected_booking["id"]).execute()
                st.success("Booking approved!")
                st.rerun()

    # Reject
    with action_col2:
        reject_reason = st.text_input("Reject reason (optional)", key="admin_reject_reason")
        if st.button("❌ Reject Booking", use_container_width=True, key="admin_reject_btn"):
            if selected_booking["status"] != "Pending":
                st.warning("Only Pending bookings can be rejected.")
            else:
                supabase.table("bookings").update({
                    "status": "Rejected",
                    "admin_reason": reject_reason
                }).eq("id", selected_booking["id"]).execute()
                st.success("Booking rejected!")
                st.rerun()

    # Cancel
    with action_col3:
        if st.button("Cancel Booking", use_container_width=True, key="admin_cancel_btn"):
            if selected_booking["status"] not in ["Approved", "Pending"]:
                st.warning("Only Pending/Approved bookings can be cancelled.")
            else:
                supabase.table("bookings").update({
                    "status": "Cancelled"
                }).eq("id", selected_booking["id"]).execute()
                st.success("Booking cancelled.")
                st.rerun()

    # Edit
    with action_col4:
        st.write("Edit Slot/Date/RP")

        new_date = st.date_input(
            "New Date",
            value=date.fromisoformat(selected_booking["date"]),
            key="admin_edit_date"
        )

        new_slot_label = st.selectbox(
            "New Slot",
            list(slot_map.values()),
            key="admin_edit_slot"
        )
        new_slot_id = next(k for k, v in slot_map.items() if v == new_slot_label)

        new_rp_label = st.selectbox(
            "New RP",
            list(rp_map.values()),
            key="admin_edit_rp"
        )
        new_rp_id = next(k for k, v in rp_map.items() if v == new_rp_label)

        if st.button("✏️ Save Changes", use_container_width=True, key="admin_save_edit_btn"):
            supabase.table("bookings").update({
                "date": str(new_date),
                "slot_id": new_slot_id,
                "rp_id": new_rp_id
            }).eq("id", selected_booking["id"]).execute()

            st.success("Booking updated.")
            st.rerun()
# ---------------------------
# TAB 4: FEEDBACK & REPORTS
# ---------------------------
with tabs[3]:
    st.subheader("Salesperson Feedback (Completed Sessions)")

    # -------------------------
    # Lookup tables
    # -------------------------
    subjects = supabase.table("subjects").select("id,name").execute().data or []
    schools = supabase.table("schools").select("id,name,city").execute().data or []
    rps = supabase.table("resource_persons").select("id,display_name").execute().data or []
    session_types = supabase.table("session_types").select("id,name").execute().data or []
    slots = supabase.table("slots").select("id,start_time,end_time").execute().data or []
    salespersons = supabase.table("users").select("id,email,name").eq("role", "salesperson").execute().data or []

    subject_map = {s["id"]: s["name"] for s in subjects}
    school_map = {s["id"]: s["name"] for s in schools}
    rp_map = {r["id"]: r["display_name"] for r in rps}
    st_map = {t["id"]: t["name"] for t in session_types}
    slot_map = {sl["id"]: f'{sl["start_time"]} - {sl["end_time"]}' for sl in slots}
    sp_map = {u["id"]: (u.get("name") or u.get("email")) for u in salespersons}

    # -------------------------
    # Filters
    # -------------------------
    f1, f2, f3, f4 = st.columns(4)

    with f1:
        filter_school = st.selectbox(
            "School",
            ["All"] + [sc["name"] for sc in schools],
            key="fb_filter_school"
        )

    with f2:
        filter_rp = st.selectbox(
            "RP",
            ["All"] + [rp["display_name"] for rp in rps],
            key="fb_filter_rp"
        )

    with f3:
        filter_subject = st.selectbox(
            "Subject",
            ["All"] + [s["name"] for s in subjects],
            key="fb_filter_subject"
        )

    with f4:
        filter_type = st.selectbox(
            "Session Type",
            ["All"] + [t["name"] for t in session_types],
            key="fb_filter_type"
        )

    st.divider()

    # -------------------------
    # Fetch feedback (with booking join)
    # -------------------------
    fb_res = (
        supabase.table("feedback")
        .select("""
            id, created_at, booking_id, salesperson_id,
            was_conducted, teacher_response_rating,
            engagement_rating, school_feedback, notes,
            bookings (
                date, subject_id, slot_id, school_id,
                rp_id, session_type_id, topic, title_name
            )
        """)
        .order("created_at", desc=True)
        .execute()
    )

    fb_rows = fb_res.data or []

    if not fb_rows:
        st.info("No feedback submitted yet.")
        st.stop()

    # -------------------------
    # Convert to flat rows
    # -------------------------
    flat = []
    for f in fb_rows:
        b = f.get("bookings") or {}

        row = {
            "Date": b.get("date"),
            "Slot": slot_map.get(b.get("slot_id")),
            "Subject": subject_map.get(b.get("subject_id")),
            "School": school_map.get(b.get("school_id")),
            "RP": rp_map.get(b.get("rp_id")),
            "Session Type": st_map.get(b.get("session_type_id")),
            "Topic": b.get("topic"),
            "Title Name": b.get("title_name"),
            "Salesperson": sp_map.get(f.get("salesperson_id")),
            "Was Conducted": f.get("was_conducted"),
            "Teacher Response Rating": f.get("teacher_response_rating"),
            "Engagement Rating": f.get("engagement_rating"),
            "School Feedback": f.get("school_feedback"),
            "Notes": f.get("notes"),
            "Submitted At": f.get("created_at"),
            "Booking ID": f.get("booking_id"),
        }
        flat.append(row)

    df = pd.DataFrame(flat)

    # -------------------------
    # Apply filters locally
    # -------------------------
    if filter_school != "All":
        df = df[df["School"] == filter_school]

    if filter_rp != "All":
        df = df[df["RP"] == filter_rp]

    if filter_subject != "All":
        df = df[df["Subject"] == filter_subject]

    if filter_type != "All":
        df = df[df["Session Type"] == filter_type]

    if df.empty:
        st.warning("No feedback matched your filters.")
        st.stop()

    st.dataframe(df, use_container_width=True)

    # Optional export button (CSV)
    st.download_button(
        "⬇️ Download Feedback CSV",
        data=df.to_csv(index=False),
        file_name="cordova_feedback.csv",
        mime="text/csv"
    )
# ---------------------------
# TAB 5: TEACHERS / ABSENCE
# ---------------------------
with tabs[4]:
    st.subheader("Teacher (RP) Absence Management")

    # Lookups
    rps = supabase.table("resource_persons").select("id, display_name, is_active").order("display_name").execute().data or []
    slots = supabase.table("slots").select("id, start_time, end_time, is_active").order("start_time").execute().data or []
    session_types = supabase.table("session_types").select("id, name").order("name").execute().data or []

    rp_map = {r["display_name"]: r["id"] for r in rps}
    slot_map = {f'{s["start_time"]} - {s["end_time"]}': s["id"] for s in slots}
    st_map = {t["name"]: t["id"] for t in session_types}

    st.markdown("### Mark RP Absent")

    c1, c2, c3 = st.columns(3)

    with c1:
        rp_name = st.selectbox("Select RP*", ["Select RP"] + list(rp_map.keys()), key="abs_rp")

    with c2:
        abs_date = st.date_input("Absent Date*", value=None, key="abs_date")

    with c3:
        abs_type = st.selectbox(
            "Absence Type*",
            ["Full Day", "Specific Slot", "Specific Session Type"],
            key="abs_type"
        )

    selected_slot_id = None
    selected_st_id = None

    if abs_type == "Specific Slot":
        slot_label = st.selectbox("Select Slot*", ["Select Slot"] + list(slot_map.keys()), key="abs_slot")
        if slot_label != "Select Slot":
            selected_slot_id = slot_map[slot_label]

    if abs_type == "Specific Session Type":
        st_label = st.selectbox("Select Session Type*", ["Select Type"] + list(st_map.keys()), key="abs_st")
        if st_label != "Select Type":
            selected_st_id = st_map[st_label]

    reason = st.text_input("Reason (optional)", key="abs_reason")

    if st.button("✅ Mark Absent", use_container_width=True, key="abs_submit"):
        if rp_name == "Select RP":
            st.error("Please select RP.")
        elif not abs_date:
            st.error("Please select date.")
        elif abs_type == "Specific Slot" and not selected_slot_id:
            st.error("Please select slot.")
        elif abs_type == "Specific Session Type" and not selected_st_id:
            st.error("Please select session type.")
        else:
            payload = {
                "rp_id": rp_map[rp_name],
                "date": str(abs_date),
                "is_full_day": abs_type == "Full Day",
                "slot_id": selected_slot_id,
                "session_type_id": selected_st_id,
                "reason": reason
            }

            # prevent duplicate exact records
            existing = (
                supabase.table("rp_unavailability")
                .select("id")
                .eq("rp_id", payload["rp_id"])
                .eq("date", payload["date"])
                .eq("is_full_day", payload["is_full_day"])
                .eq("slot_id", payload["slot_id"])
                .eq("session_type_id", payload["session_type_id"])
                .execute()
            )

            if existing.data:
                st.warning("This absence record already exists.")
            else:
                supabase.table("rp_unavailability").insert(payload).execute()
                st.success("RP marked absent successfully.")
                st.rerun()

    st.divider()
    st.markdown("### Current Absences")

    abs_res = (
        supabase.table("rp_unavailability")
        .select("id, date, is_full_day, slot_id, session_type_id, reason, rp_id, created_at")
        .order("date", desc=True)
        .execute()
    )
    abs_rows = abs_res.data or []

    if not abs_rows:
        st.info("No absences marked yet.")
        st.stop()

    # Build readable view
    rp_id_to_name = {r["id"]: r["display_name"] for r in rps}
    slot_id_to_label = {s["id"]: f'{s["start_time"]} - {s["end_time"]}' for s in slots}
    st_id_to_name = {t["id"]: t["name"] for t in session_types}

    view = []
    for a in abs_rows:
        view.append({
            "RP": rp_id_to_name.get(a["rp_id"]),
            "Date": a["date"],
            "Full Day": a["is_full_day"],
            "Slot": slot_id_to_label.get(a["slot_id"]) if a.get("slot_id") else "-",
            "Session Type": st_id_to_name.get(a["session_type_id"]) if a.get("session_type_id") else "-",
            "Reason": a.get("reason") or "",
            "Absence ID": a["id"]
        })

    df_abs = pd.DataFrame(view)
    st.dataframe(df_abs, use_container_width=True)

    st.divider()
    st.markdown("### Remove Absence")

    absence_options = [
        f'{row["RP"]} | {row["Date"]} | FullDay={row["Full Day"]} | {row["Slot"]} | {row["Session Type"]} | {row["Absence ID"][:6]}'
        for row in view
    ]

    selected_abs_label = st.selectbox("Select absence to remove", absence_options, key="abs_remove_select")
    selected_abs_idx = absence_options.index(selected_abs_label)
    selected_abs_id = view[selected_abs_idx]["Absence ID"]

    if st.button("🗑️ Delete Absence", use_container_width=True, key="abs_remove_btn"):
        supabase.table("rp_unavailability").delete().eq("id", selected_abs_id).execute()
        st.success("Absence removed. RP is available again.")
        st.rerun()
