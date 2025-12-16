import streamlit as st
from config.settings import SESSION_KEYS
from utils.auth import login_public_user, set_logged_in, logout
from db.connection import get_supabase, get_supabase_admin

st.title("Cordova Publications Online Booking Portal")
st.subheader("Login")

supabase = get_supabase()
supabase_admin = get_supabase_admin()

if st.session_state.get(SESSION_KEYS["logged_in"]):
    user = st.session_state.get(SESSION_KEYS["user_row"]) or {}
    st.success(f"Logged in as {user.get('email')} ({user.get('role')})")
    if st.button("Logout", use_container_width=True):
        logout()
        st.rerun()
    st.stop()

st.page_link("pages/0_Register.py", label="New user? Register here", icon="📝")
st.divider()

role_label = st.selectbox("Login as", ["Salesperson", "Resource Person (RP)", "Admin"])
role = "salesperson" if role_label == "Salesperson" else ("rp" if role_label.startswith("Resource") else "admin")

email = st.text_input("Email").strip().lower()
password = st.text_input("Password", type="password")

if st.button("Login", use_container_width=True):
    if not email or not password:
        st.error("Enter email and password.")
        st.stop()

    # ADMIN LOGIN
    if role == "admin":
        res = (
            supabase_admin.table("users")
            .select("*")
            .ilike("email", email)
            .eq("role", "admin")
            .limit(1)
            .execute()
        )

        rows = res.data or []
        if not rows:
            st.error("Admin not found in users table.")
            st.stop()

        admin_row = rows[0]

        if admin_row.get("is_active") is False:
            st.error("Admin account is inactive.")
            st.stop()

        # TEMP: admin password stored plain in password_hash
        if str(admin_row.get("password_hash") or "") != str(password):
            st.error("Incorrect password.")
            st.stop()

        set_logged_in("admin", email, admin_row, {})
        st.success("Admin login successful!")
        st.rerun()

    # SALESPERSON / RP LOGIN
    else:
        try:
            user_row = login_public_user(email, password)
            db_role = (user_row.get("role") or "").lower()
            if db_role != role:
                st.error(f"This account is registered as '{db_role}', not '{role}'.")
                st.stop()

            set_logged_in(role, email, user_row, {})
            st.success("Login successful!")
            st.rerun()

        except Exception as e:
            st.error(str(e))
