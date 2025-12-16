# utils/auth.py
import streamlit as st
import hashlib
import hmac
import base64
import secrets
from db.connection import get_supabase_admin
from config.settings import SESSION_KEYS

# ----------------------------
# Password Hashing (PBKDF2)
# Stored format:
# pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
# ----------------------------
PBKDF2_ITERATIONS = 180_000


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=32
    )
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    dk_b64 = base64.b64encode(dk).decode("utf-8")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_b64}${dk_b64}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, dk_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False

        iters = int(iters)
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        dk_expected = base64.b64decode(dk_b64.encode("utf-8"))

        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iters,
            dklen=len(dk_expected)
        )
        return hmac.compare_digest(dk, dk_expected)
    except Exception:
        return False


# ----------------------------
# USERS TABLE HELPERS (RLS SAFE)
# Always use service-role client for users table.
# ----------------------------
def get_public_user_by_email(email: str):
    email = (email or "").strip().lower()
    supabase_admin = get_supabase_admin()

    res = (
        supabase_admin.table("users")
        .select("*")
        .ilike("email", email)  # case-insensitive match
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def register_public_user(name: str, email: str, phone: str, region: str, role: str, password: str):
    """
    Creates a new row in public.users with hashed password.
    Option B: user can login immediately (is_active default true in DB).
    RLS Safe: uses service role client.
    """
    supabase_admin = get_supabase_admin()

    email = (email or "").strip().lower()

    existing = get_public_user_by_email(email)
    if existing:
        raise ValueError("This email is already registered.")

    password_hash = _hash_password(password)

    res = (
        supabase_admin.table("users")
        .insert({
            "name": name,
            "email": email,
            "phone": phone,
            "region": region,
            "role": role,
            "password_hash": password_hash,
            # is_active default true in DB
        })
        .execute()
    )

    row = (res.data or [None])[0]
    if not row:
        raise ValueError("Registration failed. Please try again.")
    return row


def login_public_user(email: str, password: str):
    """
    Validates email + password against public.users.
    Returns user_row if success.
    RLS Safe: uses service role client for lookup.
    """
    email = (email or "").strip().lower()
    user_row = get_public_user_by_email(email)

    if not user_row:
        raise ValueError("No account found with this email. Please register first.")

    stored = str(user_row.get("password_hash") or "")
    if not stored:
        raise ValueError("Password not set for this account. Please contact Admin.")

    # Only PBKDF2 hashes are supported here (Salesperson/RP)
    if not _verify_password(password, stored):
        raise ValueError("Incorrect password.")

    return user_row


def set_logged_in(role: str, email: str, user_row: dict, auth_user: dict = None):
    st.session_state[SESSION_KEYS["role"]] = role
    st.session_state[SESSION_KEYS["email"]] = (email or "").strip().lower()
    st.session_state[SESSION_KEYS["user_row"]] = user_row
    st.session_state[SESSION_KEYS["auth_user"]] = auth_user or {}
    st.session_state[SESSION_KEYS["logged_in"]] = True


def logout():
    for k in SESSION_KEYS.values():
        st.session_state.pop(k, None)
