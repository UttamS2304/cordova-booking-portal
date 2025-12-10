# app.py
import streamlit as st
from config.settings import SESSION_KEYS

# -------------------------
# Supabase setup (needed here to read magic link tokens)
# -------------------------
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

st.set_page_config(
    page_title="Cordova Publications | Online Booking Portal",
    layout="wide"
)

# -------------------------
# NEW Helper: Handle magic link return tokens
# -------------------------
def handle_magic_login():
    access_token = st.query_params.get("access_token")
    refresh_token = st.query_params.get("refresh_token")
    link_type = st.query_params.get("type")

    # Only run when user comes from magic link
    if access_token and refresh_token and link_type == "magiclink":
        try:
            supabase.auth.set_session(access_token, refresh_token)
            user_res = supabase.auth.get_user()

            if user_res and user_res.user:
                # Store login in session
                st.session_state[SESSION_KEYS["logged_in"]] = True
                st.session_state[SESSION_KEYS["user_email"]] = user_res.user.email

                # If your login page stores a "user_row",
                # you can fetch it here too (optional but recommended)
                try:
                    row = (
                        supabase.table("profiles")
                        .select("*")
                        .eq("email", user_res.user.email)
                        .single()
                        .execute()
                    )
                    if row.data:
                        st.session_state[SESSION_KEYS["user_row"]] = row.data
                except:
                    pass

                # Clean URL (remove tokens)
                st.query_params.clear()
                st.rerun()

        except Exception as e:
            st.error(f"Magic link login failed: {e}")

# ✅ Run this BEFORE redirect check
handle_magic_login()

# -------------------------
# Helper: Redirect logged-in users
# -------------------------
def redirect_if_logged_in():
    if st.session_state.get(SESSION_KEYS["logged_in"]):
        user_row = st.session_state.get(SESSION_KEYS["user_row"], {})
        role = (user_row.get("role") or "").lower()

        if role == "salesperson":
            st.switch_page("pages/2_Salesperson.py")
        elif role == "admin":
            st.switch_page("pages/3_Admin.py")
        elif role == "rp":
            st.switch_page("pages/4_RP.py")
        else:
            # If role is missing or unknown, send to login
            st.switch_page("pages/1_Login.py")

redirect_if_logged_in()

# -------------------------
# Landing Page UI
# -------------------------
st.markdown(
    """
    <div style="text-align:center; padding-top: 40px;">
        <h1 style="font-size: 48px;">Cordova Publications Online Booking Portal</h1>
        <p style="font-size: 18px; color: #cfcfcf; margin-top: 8px;">
            Welcome! Book Live Classes, Product Trainings and AVRD sessions quickly and track them in one place.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("")
st.write("")
col1, col2, col3 = st.columns([1, 1, 1])

with col2:
    if st.button("🔐 Login to Continue", use_container_width=True):
        st.switch_page("pages/1_Login.py")

st.write("")
st.write("")

# -------------------------
# Footer
# -------------------------
st.markdown(
    """
    <hr>
    <div style="text-align:center; font-size: 13px; color: #888;">
        Made by @Uttam for Cordova Publications 2025
    </div>
    """,
    unsafe_allow_html=True
)
