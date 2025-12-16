import streamlit as st
import pandas as pd
from datetime import date
from config.settings import SESSION_KEYS
from db.connection import get_supabase
from utils.auth import logout

st.title("Admin Dashboard")

# --- Access control: only admin can open ---
if not st.session_state.get(SESSION_KEYS["logged_in"]):
    st.warning("Please login first.")
    st.stop()

user_row = st.session_state.get(SESSION_KEYS["user_row"], {})
if (user_row.get("role") or "").lower() != "admin":
    st.error("You are not authorized to view this page.")
    st.stop()

supabase = get_supabase()

# --- Sidebar ---
with st.sidebar:
    st.subheader("Admin Controls")
    st.write(f"Logged in as: **{user_row.get('email')}**")
    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()

tabs = st.tabs([
    "Home",
    "User Approvals",
    "Bookings",
    "Feedback & Reports",
    "Teachers",
    "RP Linking"
])

def safe_tab(fn):
    """Prevents one tab error from crashing whole admin page."""
    try:
        fn()
    except Exception as e:
        st.error("This tab crashed due to a database/schema mismatch.")
        st.code(str(e))

# ---------------------------
# TAB 1: ADMIN HOME DASHBOARD
# ---------------------------
def tab_home():
    st.subheader("Admin Home Dashboard")

    today_str = str(date.today())

    today_rows = (
        supabase.table("bookings")
        .select("id, status, subject_id, rp_id, slot_id, session_type_id, school_id, date")
        .eq("date", today_str)
        .execute()
    ).data or []

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

    st.markdown("### Subject-wise Booking Count (Today)")
    subj_counts = {}
    for b in today_rows:
        name = subject_map.get(b.get("subject_id"), "Unknown")
        subj_counts[name] = subj_counts.get(name, 0) + 1
    df_subj = pd.DataFrame([{"Subject": k, "Bookings": v} for k, v in subj_counts.items()])
    if df_subj.empty:
        st.info("No bookings today.")
    else:
        st.dataframe(df_subj.sort_values("Bookings", ascending=False), use_container_width=True)

    st.divider()

    st.markdown("### RP-wise Load Summary (Today)")
    rp_counts = {}
    for b in today_rows:
        name = rp_map.get(b.get("rp_id"), "Unassigned")
        rp_counts[name] = rp_counts.get(name, 0) + 1
    df_rp = pd.DataFrame([{"RP": k, "Classes Today": v} for k, v in rp_counts.items()])
    if df_rp.empty:
        st.info("No RP load yet.")
    else:
        st.dataframe(df_rp.sort_values("Classes Today", ascending=False), use_container_width=True)

    st.divider()

    st.markdown("### Today's Absent Teachers")
    abs_rows = (
        supabase.table("rp_unavailability")
        .select("rp_id, date, is_full_day, slot_id, session_type_id")
        .eq("date", today_str)
        .execute()
    ).data or []

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

    st.markdown("### Next 3 Upcoming Sessions")
    upcoming = (
        supabase.table("bookings")
        .select("id, date, status, subject_id, rp_id, slot_id, session_type_id, school_id, topic")
        .gte("date", today_str)
        .in_("status", ["Approved", "Scheduled", "Pending"])
        .order("date", desc=False)
        .limit(3)
        .execute()
    ).data or []

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

with tabs[0]:
    safe_tab(tab_home)

# ---------------------------
# TAB 2: USER APPROVALS
# ---------------------------
def tab_users():
    st.subheader("Pending User Approvals")

    pending_users = (
        supabase.table("users")
        .select("id, name, email, role, is_active, created_at")
        .eq("is_active", False)
        .in_("role", ["salesperson", "rp"])
        .order("created_at", desc=True)
        .execute()
    ).data or []

    if not pending_users:
        st.success("No pending users right now.")
        return

    df = pd.DataFrame(pending_users)
    st.dataframe(df, use_container_width=True)

    st.divider()
    options = [f'{u["email"]} ({u["role"]})' for u in pending_users]
    selected = st.selectbox("Select a pending user", options, key="pending_user_select")
    selected_user = pending_users[options.index(selected)]

    colA, colB = st.columns(2)
    with colA:
        if st.button("✅ Approve User", use_container_width=True):
            supabase.table("users").update({"is_active": True}).eq("id", selected_user["id"]).execute()
            st.success(f"Approved: {selected_user['email']}")
            st.rerun()

    with colB:
        if st.button("❌ Reject/Delete User", use_container_width=True):
            supabase.table("users").delete().eq("id", selected_user["id"]).execute()
            st.warning(f"Deleted: {selected_user['email']}")
            st.rerun()

with tabs[1]:
    safe_tab(tab_users)

# ---------------------------
# TAB 3: BOOKINGS
# ---------------------------
def tab_bookings():
    st.subheader("All Bookings")

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

    filter_status = st.selectbox("Status", ["All", "Pending", "Approved", "Rejected", "Cancelled", "Completed"])

    q = supabase.table("bookings").select("*").order("date", desc=True)
    if filter_status != "All":
        q = q.eq("status", filter_status)

    rows = (q.execute().data or [])
    if not rows:
        st.info("No bookings found.")
        return

    df = pd.DataFrame(rows)
    if "subject_id" in df.columns:
        df["Subject"] = df["subject_id"].map(subject_map)
    if "school_id" in df.columns:
        df["School"] = df["school_id"].map(school_map)
    if "rp_id" in df.columns:
        df["RP"] = df["rp_id"].map(rp_map)
    if "session_type_id" in df.columns:
        df["Session Type"] = df["session_type_id"].map(st_map)
    if "slot_id" in df.columns:
        df["Slot"] = df["slot_id"].map(slot_map)
    if "salesperson_id" in df.columns:
        df["Salesperson"] = df["salesperson_id"].map(sp_map)

    st.dataframe(df, use_container_width=True)

with tabs[2]:
    safe_tab(tab_bookings)

# ---------------------------
# TAB 4: FEEDBACK
# ---------------------------
def tab_feedback():
    st.subheader("Feedback & Reports")

    fb = supabase.table("feedback").select("*").order("created_at", desc=True).execute().data or []
    if not fb:
        st.info("No feedback yet.")
        return
    st.dataframe(pd.DataFrame(fb), use_container_width=True)

with tabs[3]:
    safe_tab(tab_feedback)

# ---------------------------
# TAB 5: TEACHERS
# ---------------------------
def tab_teachers():
    st.subheader("Teachers / RP")

    rps = supabase.table("resource_persons").select("*").order("display_name").execute().data or []
    if not rps:
        st.info("No RPs found.")
        return
    st.dataframe(pd.DataFrame(rps), use_container_width=True)

with tabs[4]:
    safe_tab(tab_teachers)

# ---------------------------
# TAB 6: RP LINKING (NO email column required)
# ---------------------------
def tab_rp_linking():
    st.subheader("RP Linking (Manual)")

    rp_users = (
        supabase.table("users")
        .select("id,email,name,role")
        .eq("role", "rp")
        .order("email")
        .execute()
    ).data or []

    rp_profiles = (
        supabase.table("resource_persons")
        .select("id,display_name,user_id")
        .order("display_name")
        .execute()
    ).data or []

    if not rp_users:
        st.warning("No RP users found in users table.")
        return
    if not rp_profiles:
        st.warning("No RP profiles found in resource_persons table.")
        return

    user_labels = [f'{u["email"]} ({u.get("name") or "No Name"})' for u in rp_users]
    profile_labels = [f'{p["display_name"]} | linked={("YES" if p.get("user_id") else "NO")}' for p in rp_profiles]

    c1, c2 = st.columns(2)
    with c1:
        selected_user_label = st.selectbox("RP Login (users)", user_labels)
    with c2:
        selected_profile_label = st.selectbox("RP Profile (resource_persons)", profile_labels)

    selected_user = rp_users[user_labels.index(selected_user_label)]
    selected_profile = rp_profiles[profile_labels.index(selected_profile_label)]

    if st.button("🔗 Link", use_container_width=True):
        supabase.table("resource_persons").update({
            "user_id": selected_user["id"]
        }).eq("id", selected_profile["id"]).execute()

        st.success("Linked successfully.")
        st.rerun()

with tabs[5]:
    safe_tab(tab_rp_linking)
