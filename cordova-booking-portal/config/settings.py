# config/settings.py

ROLES = {
    "salesperson": "Salesperson",
    "rp": "Resource Person (RP)",
    "admin": "Admin (Coordinator)",
}

USER_STATUS = {
    "pending": "Pending Approval",
    "active": "Active",
}

SESSION_KEYS = {
    "role": "role",
    "email": "email",
    "logged_in": "logged_in",
    "user_row": "user_row",          # row from public.users table
    "auth_user": "auth_user",        # supabase auth user
}
