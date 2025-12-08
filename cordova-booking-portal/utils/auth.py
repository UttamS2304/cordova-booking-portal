# utils/auth.py
import streamlit as st
from db.connection import get_supabase
from config.settings import SESSION_KEYS


def send_magic_link(email: str):
    """
    Sends a Supabase magic link to the email.
    """
    supabase = get_supabase()
    supabase.auth.sign_in_with_otp({
        "email": email,
        "options": {
            "should_create_user": True
        }
    })


def get_public_user_by_email(email: str):
    """
    Reads public.users row by email.
    """
    supabase = get_supabase()
    res = supabase.table("users").select("*").eq("email", email).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def create_pending_public_user(email: str, role: str):
    """
    Creates a new row in public.users as pending (is_active=false).
    """
    supabase = get_supabase()
    res = supabase.table("users").insert({
        "email": email,
        "role": role,
        "is_active": False,
        "name": email.split("@")[0],  # temporary name
    }).execute()
    return (res.data or [None])[0]


def ensure_public_user(email: str, role: str):
    """
    If user exists in public.users return it.
    If not, create pending user.
    """
    user_row = get_public_user_by_email(email)
    if user_row:
        return user_row
    return create_pending_public_user(email, role)


def auto_link_rp_user(email: str, public_user_id: str):
    """
    Auto-link RP public.users -> resource_persons
    based on matching email.
    """
    supabase = get_supabase()

    res = (
        supabase.table("resource_persons")
        .select("id, user_id")
        .eq("email", email)
        .limit(2)
        .execute()
    )

    rows = res.data or []
    if len(rows) != 1:
        return  # 0 or multiple matches -> don't guess

    rp_row = rows[0]
    if rp_row.get("user_id"):
        return  # already linked

    supabase.table("resource_persons").update({
        "user_id": public_user_id
    }).eq("id", rp_row["id"]).execute()


def set_logged_in(role: str, email: str, user_row: dict, auth_user: dict):
    st.session_state[SESSION_KEYS["role"]] = role
    st.session_state[SESSION_KEYS["email"]] = email
    st.session_state[SESSION_KEYS["user_row"]] = user_row
    st.session_state[SESSION_KEYS["auth_user"]] = auth_user
    st.session_state[SESSION_KEYS["logged_in"]] = True


def logout():
    supabase = get_supabase()
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    for k in SESSION_KEYS.values():
        st.session_state.pop(k, None)
