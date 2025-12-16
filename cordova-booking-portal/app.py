import streamlit as st
from config.settings import SESSION_KEYS

st.set_page_config(
    page_title="Cordova Publications | Online Booking Portal",
    layout="wide",
)

login_page = st.Page("pages/1_Login.py", title="Login", icon="🔐")
register_page = st.Page("pages/0_Register.py", title="Register", icon="📝")

salesperson_page = st.Page("pages/2_Salesperson.py", title="Salesperson", icon="🧑‍💼")
admin_page = st.Page("pages/3_Admin.py", title="Admin", icon="🛠️")
rp_page = st.Page("pages/4_RP.py", title="RP", icon="👩‍🏫")


def get_nav_config():
    if not st.session_state.get(SESSION_KEYS["logged_in"]):
        return {"": [login_page, register_page]}  # remove register_page if you want

    user_row = st.session_state.get(SESSION_KEYS["user_row"], {}) or {}
    role = (user_row.get("role") or "").lower()

    if role == "salesperson":
        return {"": [salesperson_page]}
    if role == "admin":
        return {"": [admin_page]}
    if role == "rp":
        return {"": [rp_page]}

    return {"": [login_page]}


nav = st.navigation(get_nav_config())
nav.run()
