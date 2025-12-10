# pages/1_Login.py
import streamlit as st
import streamlit.components.v1 as components
from config.settings import ROLES, SESSION_KEYS
from utils.auth import (
    send_magic_link,
    ensure_public_user,
    auto_link_rp_user,
    set_logged_in,
    logout
)
from db.connection import get_supabase

st.set_page_config(page_title="Login | Cordova Booking Portal", layout="centered")
st.title("Cordova Publications Online Booking Portal")
st.subheader("Login")

supabase = get_supabase()

# --------------------------------------------------------
# NEW Step 0: Convert #access_token... into ?access_token...
# Streamlit cannot read anything after '#'
# --------------------------------------------------------
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

# ------------------------------
# If already logged in
# ------------------------------
if st.session_state.get(SESSION_KEYS["logged_in"]):
    user = st.session_state.get(SESSION_KEYS["user_row"])
    st.success(f"Logged in as {user.get('email')} ({user.get('role')})")
    if st.button("Logout"):
        logout()
        st.rerun()
    st.stop()

# --------------------------------------------------------
# NEW Step 1: MAGIC LINK HANDLER (AUTO LOGIN)
# Works for:
#   A) implicit flow (?access_token=...)
#   B) PKCE flow (?code=...)
# --------------------------------------------------------
query_params = st.query_params
access_token = query_params.get("access_token")
refresh_token = query_params.get("refresh_token")
code = query_params.get("code")

if code or (access_token and refresh_token):
    try:
        # PKCE (if Supabase sends ?code=...)
        if code:
            supabase.auth.exchange_code_for_session(code)

        # Implicit (after normalize_magic_link_url)
        elif access_token and refresh_token:
            supabase.auth.set_session(access_token, refresh_token)

        auth_user_obj = supabase.auth.get_user().user
        email = auth_user_obj.email

        # Role chosen BEFORE sending magic link (may be missing on return)
        role_intent = st.session_state.get("login_role_intent")

        # Ensure public.users row exists.
        # If role_intent missing, default salesperson BUT do not overwrite existing role.
        user_row = ensure_public_user(email, role_intent or "salesperson")

        # If DB already has a role, trust that
        db_role = (user_row.get("role") or "").lower()
        role = db_role if db_role else (role_intent or "salesperson")

        if not user_row.get("is_active"):
            st.warning("Your account is pending admin approval.")
            st.stop()

        # Auto link if RP
        if role == "rp":
            auto_link_rp_user(email, user_row["id"])

        set_logged_in(role, email, user_row, auth_user_obj.model_dump())
        st.success("Login successful via magic link!")

        # Clear tokens from URL so it doesn't re-run
        st.query_params.clear()
        st.rerun()

    except Exception as e:
        st.error(f"Magic link login failed: {e}")
        st.query_params.clear()
        st.stop()

st.divider()

# ------------------------------
# Role selection
# ------------------------------
role_label = st.selectbox("Login as", list(ROLES.values()))
role = [k for k, v in ROLES.items() if v == role_label][0]

st.divider()

# ------------------------------
# Salesperson / RP Magic Link Login
# ------------------------------
if role in ("salesperson", "rp"):
    email = st.text_input("Enter your email")

    if st.button("Send Magic Link", use_container_width=True):
        if not email:
            st.error("Please enter email.")
        else:
            try:
                # Save which role they chose BEFORE sending link
                st.session_state["login_role_intent"] = role

                send_magic_link(email)
                st.success("Magic link sent! Please check your email and click the link.")
                st.info("After clicking the link, you will return here and be logged in automatically.")
            except Exception as e:
                st.error(f"Failed to send magic link: {e}")

# ------------------------------
# Admin Password Login
# ------------------------------
else:
    admin_email = st.text_input("Admin Email")
    admin_password = st.text_input("Admin Password", type="password")

    if st.button("Login", use_container_width=True):
        if not admin_email or not admin_password:
            st.error("Enter email and password.")
        else:
            res = (
                supabase.table("users")
                .select("*")
                .eq("email", admin_email)
                .eq("role", "admin")
                .limit(1)
                .execute()
            )

            rows = res.data or []
            if not rows:
                st.error("Admin not found.")
                st.stop()

            admin_row = rows[0]
            if not admin_row.get("is_active"):
                st.error("Admin account is inactive.")
                st.stop()

            # TEMP plain-text compare (we will hash later)
            if str(admin_row.get("password_hash")) != str(admin_password):
                st.error("Incorrect password.")
                st.stop()

            set_logged_in("admin", admin_email, admin_row, {})
            st.success("Admin login successful!")
            st.rerun()
