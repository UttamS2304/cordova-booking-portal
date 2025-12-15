# pages/1_Login.py
import streamlit as st
from config.settings import ROLES, SESSION_KEYS
from utils.auth import login_public_user, set_logged_in, logout

st.set_page_config(page_title="Login | Cordova Booking Portal", layout="centered")
st.title("Cordova Publications Online Booking Portal")
st.subheader("Login")

# If already logged in
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

    try:
        user_row = login_public_user(email, password)

        # Role check: must match selected role
        db_role = (user_row.get("role") or "").lower()
        if db_role != role:
            st.error(f"This account is registered as '{db_role}', not '{role}'.")
            st.stop()

        # Optional: if you still want to block inactive accounts even in Option B, uncomment:
        # if not user_row.get("is_active"):
        #     st.warning("Your account is inactive. Please contact Admin.")
        #     st.stop()

        set_logged_in(role, email, user_row, {})
        st.success("Login successful!")
        st.rerun()

    except Exception as e:
        st.error(str(e))
