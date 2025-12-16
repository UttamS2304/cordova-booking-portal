# app.py
import streamlit as st
from config.settings import SESSION_KEYS

st.set_page_config(
    page_title="Cordova Publications | Online Booking Portal",
    layout="wide"
)

# -------------------------
# Define Pages (controlled sidebar)
# -------------------------
login_page = st.Page("pages/1_Login.py", title="Login", icon="🔐")

# Optional: keep registration visible only before login
register_page = st.Page("pages/0_Register.py", title="Register", icon="📝")

salesperson_page = st.Page("pages/2_Salesperson.py", title="Salesperson", icon="🧑‍💼")
admin_page = st.Page("pages/3_Admin.py", title="Admin", icon="🛠️")
rp_page = st.Page("pages/4_RP.py", title="RP", icon="👩‍🏫")

# -------------------------
# Role-based Navigation
# -------------------------
def get_nav_config():
    # Not logged in -> only Login (+ Register if you want)
    if not st.session_state.get(SESSION_KEYS["logged_in"]):
        return {"": [login_page, register_page]}  # remove register_page if you don't want it shown

    # Logged in -> show ONLY their role page
    user_row = st.session_state.get(SESSION_KEYS["user_row"], {}) or {}
    role = (user_row.get("role") or "").lower()

    if role == "salesperson":
        return {"": [salesperson_page]}
    elif role == "admin":
        return {"": [admin_page]}
    elif role == "rp":
        return {"": [rp_page]}
    else:
        # Unknown role -> send to login
        return {"": [login_page]}

nav = st.navigation(get_nav_config())
nav.run()
