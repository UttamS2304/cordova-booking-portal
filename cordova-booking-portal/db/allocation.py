# db/allocation.py
from datetime import date as dt_date
from db.connection import get_supabase

STATUS_BLOCKING = ["Pending", "Approved", "Scheduled", "Completed"]

def _is_saturday(d):
    if isinstance(d, str):
        d = dt_date.fromisoformat(d)
    return d.weekday() == 5  # Saturday

def _fetch_slots_ordered():
    supabase = get_supabase()
    res = (
        supabase.table("slots")
        .select("id, start_time, end_time")
        .eq("is_active", True)
        .order("start_time")
        .execute()
    )
    return res.data or []

def _adjacent_slot_ids(slots, slot_id):
    ids = [s["id"] for s in slots]
    if slot_id not in ids:
        return []
    i = ids.index(slot_id)
    adj = []
    if i - 1 >= 0: adj.append(ids[i-1])
    if i + 1 < len(ids): adj.append(ids[i+1])
    return adj

def _count_bookings(filters: dict):
    supabase = get_supabase()
    q = supabase.table("bookings").select("id, status")
    for k, v in filters.items():
        q = q.eq(k, v)
    res = q.execute()
    rows = res.data or []
    rows = [r for r in rows if r.get("status") in STATUS_BLOCKING]
    return len(rows)

def _rp_is_absent(rp_id, booking_date, slot_id=None, session_type_id=None):
    supabase = get_supabase()
    try:
        q = (
            supabase.table("rp_unavailability")
            .select("id, is_full_day, slot_id, session_type_id")
            .eq("rp_id", rp_id)
            .eq("date", booking_date)
        )
        res = q.execute()
    except Exception:
        return False  # if table not created yet, ignore absence

    rows = res.data or []
    for r in rows:
        if r.get("is_full_day"):
            return True
        if slot_id and r.get("slot_id") == slot_id:
            return True
        if session_type_id and r.get("session_type_id") == session_type_id:
            return True
    return False

def assign_rp(subject_id, slot_id, booking_date, session_type_id, school_id):
    supabase = get_supabase()

    # Session type
    st_res = (
        supabase.table("session_types")
        .select("id, name")
        .eq("id", session_type_id)
        .limit(1)
        .execute()
    )
    st_row = (st_res.data or [None])[0]
    if not st_row:
        return None

    is_avrd = (st_row.get("name") or "").strip().upper() == "AVRD"
    is_sat = _is_saturday(booking_date)

    # Rule: max 4 parallel per slot
    if _count_bookings({"date": booking_date, "slot_id": slot_id}) >= 4:
        return None

    # Rule: max 2 per school per day
    if _count_bookings({"date": booking_date, "school_id": school_id}) >= 2:
        return None

    slots = _fetch_slots_ordered()
    adjacent_ids = _adjacent_slot_ids(slots, slot_id)

    # Priority list from rp_subject_rules
    rules_res = (
        supabase.table("rp_subject_rules")
        .select("rp_id, priority, max_classes_per_day, is_saturday, is_avrd")
        .eq("subject_id", subject_id)
        .eq("is_saturday", is_sat)
        .eq("is_avrd", is_avrd)
        .order("priority")
        .execute()
    )
    rules = rules_res.data or []
    if not rules:
        return None

    global_max = 2 if is_sat else 3

    for rule in rules:
        rp_id = rule["rp_id"]
        subject_max = int(rule.get("max_classes_per_day") or 0)

        # Absence rule
        if _rp_is_absent(rp_id, booking_date, slot_id=slot_id, session_type_id=session_type_id):
            continue

        # Subject quota
        if _count_bookings({"date": booking_date, "rp_id": rp_id, "subject_id": subject_id}) >= subject_max:
            continue

        # Global quota
        if _count_bookings({"date": booking_date, "rp_id": rp_id}) >= global_max:
            continue

        # AVRD one per day per RP
        if is_avrd and _count_bookings({"date": booking_date, "rp_id": rp_id, "session_type_id": session_type_id}) >= 1:
            continue

        # Same-slot conflict
        if _count_bookings({"date": booking_date, "rp_id": rp_id, "slot_id": slot_id}) > 0:
            continue

        # Break rule: no adjacent slot for same RP
        if any(_count_bookings({"date": booking_date, "rp_id": rp_id, "slot_id": a}) > 0 for a in adjacent_ids):
            continue

        return rp_id

    return None

def available_slots_summary(subject_id, booking_date, session_type_id):
    supabase = get_supabase()
    slots = _fetch_slots_ordered()

    st_res = (
        supabase.table("session_types")
        .select("id, name")
        .eq("id", session_type_id)
        .limit(1)
        .execute()
    )
    st_row = (st_res.data or [None])[0]
    is_avrd = (st_row.get("name") or "").strip().upper() == "AVRD"
    is_sat = _is_saturday(booking_date)

    rules_res = (
        supabase.table("rp_subject_rules")
        .select("rp_id, priority, max_classes_per_day, is_saturday, is_avrd")
        .eq("subject_id", subject_id)
        .eq("is_saturday", is_sat)
        .eq("is_avrd", is_avrd)
        .order("priority")
        .execute()
    )
    rules = rules_res.data or []
    global_max = 2 if is_sat else 3

    summary = []
    for s in slots:
        slot_id = s["id"]
        booked_here = _count_bookings({"date": booking_date, "slot_id": slot_id})
        remaining_parallel = max(0, 4 - booked_here)

        adjacent_ids = _adjacent_slot_ids(slots, slot_id)

        possible = 0
        for r in rules:
            rp_id = r["rp_id"]
            subject_max = int(r.get("max_classes_per_day") or 0)

            if _rp_is_absent(rp_id, booking_date, slot_id=slot_id, session_type_id=session_type_id):
                continue
            if _count_bookings({"date": booking_date, "rp_id": rp_id}) >= global_max:
                continue
            if _count_bookings({"date": booking_date, "rp_id": rp_id, "slot_id": slot_id}) > 0:
                continue
            if any(_count_bookings({"date": booking_date, "rp_id": rp_id, "slot_id": a}) > 0 for a in adjacent_ids):
                continue
            if _count_bookings({"date": booking_date, "rp_id": rp_id, "subject_id": subject_id}) >= subject_max:
                continue
            if is_avrd and _count_bookings({"date": booking_date, "rp_id": rp_id, "session_type_id": session_type_id}) >= 1:
                continue

            possible += 1

        summary.append({
            "slot_id": slot_id,
            "start_time": s["start_time"],
            "end_time": s["end_time"],
            "remaining_parallel": remaining_parallel,
            "possible_rps": possible
        })

    return summary
