# app.py
import streamlit as st
import streamlit.components.v1 as components
from config.settings import SESSION_KEYS
from supabase import create_client

# -------------------------
# Supabase setup
# -------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

st.set_page_config(
    page_title="Cordova Publications | Online Booking Portal",
    layout="wide"
)

# -------------------------
# NEW Step 0: Move tokens from URL hash (#) to query (?)
# Streamlit can't read hash, so we convert it.
# -------------------------
def normalize_magic_link_url():
    components.html(
        """
        <script>
        const hash = window.location.hash.substring(1);
        if (hash && hash.includes("access_token")) {
            const params = new URLSearchParams(hash);
            const access_token = params.get("access_token");
            const refresh_token = params.get("refresh_token");
            const type = params.get("type") || "magiclink";

            if (access_token && refresh_token) {
                const url = new URL(window.location.href);
                url.searchParams.set("access_token", access_token);
                url.searchParams.set("refresh_token", refresh_token);
                url.searchParams.set("type", type);
                url.hash = "";
                window.location.replace(url.toString());
            }
        }
        </script>
        """,
        height=0
    )

normalize_magic_link_url()

# -------------------------
# NEW Step 1: Handle magic link return
# Works for both PKCE (?code=) or implicit (?access_token=)
# -------------------------
def handle_magic_login():
    qp = st.query_params

    code = qp.get("code")
    access_token = qp.get("access_token")
    refresh_token = qp.get("refresh_token")

    try:
        # PKCE flow (if Supabase returns ?code=...)
        if code:
            supabase.auth.exchange_code_for_session(code)

        # Implicit flow (after normalize_magic_link_url)
        elif access_token and refresh_token:
            supabase.auth.set_session(access_token, refresh_token)

        else:
            return  # nothing to do

        user_res = supabase.auth.get_user()
        if not user_res or not user_res.user:
            return

        email = user_res.user.email

        # Mark logged in
        st.session_state[SESSION_KEYS["logged_in"]] = True
        st.session_state[SESSION_KEYS["user_email"]] = email

        # ---- Try to get role from metadata first ----
        role = None
        try:
            role = (user_res.user.app_metadata or {}).get("role") \
                or (user_res.user.user_metadata or {}).get("role")
        except:
            pass

        # ---- If no role in metadata, fetch from DB tables ----
        user_row = None
        if not role:
            for table in ["profiles", "users", "admins", "salespersons", "rp_users"]:
                try:
                    r = (
                        supabase.table(table)
                        .select("*")
                        .eq("email", email)
                        .single()
                        .execute()
                    )
                    if r.data:
                        user_row = r.data
                        role = (user_row.get("role") or "").lower()
                        break
                except:
                    continue

        if user_row:
            st.session_state[SESSION_KEYS["user_row"]] = user_row
        else:
            st.session_state[SESSION_KEYS["user_row"]] = {"email": email, "role": role or ""}

        # Clear URL tokens
        st.query_params.clear()
        st.rerun()

    except Exception as e:
        st.error(f"Magic link login failed: {e}")

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
