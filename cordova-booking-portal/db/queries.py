import pandas as pd
from db.connection import get_supabase

def fetch_subjects():
    supabase = get_supabase()
    res = supabase.table("subjects").select("id,name").eq("is_active", True).order("name").execute()
    return pd.DataFrame(res.data or [])

def fetch_session_types():
    supabase = get_supabase()
    res = supabase.table("session_types").select("id,name,duration_minutes").eq("is_active", True).order("name").execute()
    return pd.DataFrame(res.data or [])

def fetch_slots():
    supabase = get_supabase()
    res = supabase.table("slots").select("id,start_time,end_time,duration_minutes").eq("is_active", True).order("start_time").execute()
    return pd.DataFrame(res.data or [])
