# app.py
import streamlit as st
from config.settings import SESSION_KEYS

st.set_page_config(
    page_title="Cordova Publications | Online Booking Portal",
    layout="wide"
)

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
            # fallback: send to login
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

# Optional: Registration shortcut
colA, colB, colC = st.columns([1, 1, 1])
with colB:
    if st.button("📝 New User? Register", use_container_width=True):
        st.switch_page("pages/0_Register.py")

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
