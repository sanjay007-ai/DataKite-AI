"""Optional persistent usage analytics for DataKite AI.

Uses Supabase REST from the backend only. If Supabase environment variables are
not configured, tracking is a no-op and never breaks the user experience.
Never send uploaded business rows or passwords to analytics.
"""
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta


def _config():
    url = str(os.environ.get("SUPABASE_URL", "")).strip().rstrip("/")
    key = str(os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
    admin = str(os.environ.get("DATAKITE_ADMIN_EMAIL", "")).strip().lower()
    if not url or not key:
        return None
    return url, key, admin


def enabled():
    return _config() is not None


def is_admin(user):
    cfg = _config()
    if not cfg or not user:
        return False
    admin = cfg[2]
    return bool(admin) and str(user.get("email", "")).strip().lower() == admin


def _request(path, method="GET", payload=None, params=""):
    cfg = _config()
    if not cfg:
        return None
    url, key, _ = cfg
    full = f"{url}/rest/v1/{path}"
    if params:
        full += "?" + params
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(full, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except Exception as exc:
        print("[usage analytics] request skipped:", repr(exc))
        return None


def track_event(event_type, user=None, question=None, success=True, **metadata):
    """Best-effort event logging. Never raises into the main request."""
    if not enabled():
        return False
    user = user or {}
    row = {
        "event_type": str(event_type)[:40],
        "user_id": str(user.get("id", ""))[:100] or None,
        "user_email": str(user.get("email", ""))[:254] or None,
        "user_name": str(user.get("name", ""))[:100] or None,
        "question": str(question)[:2000] if question else None,
        "success": bool(success),
        "metadata": metadata or {},
    }
    return _request("datakite_usage_events", "POST", [row], "Prefer=return=minimal") is not None


def recent_events(days=30, limit=10000):
    if not enabled():
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, min(90, int(days))))).isoformat()
    params = (
        "select=event_type,user_id,user_email,user_name,question,success,metadata,created_at"
        f"&created_at=gte.{since}"
        f"&order=created_at.desc&limit={max(1, min(10000, int(limit)))}"
    )
    data = _request("datakite_usage_events", "GET", params=params)
    return data if isinstance(data, list) else []


def usage_summary(days=30):
    events = recent_events(days=days)
    users = {e.get("user_email") for e in events if e.get("user_email")}
    today = datetime.now(timezone.utc).date().isoformat()
    active_today = {e.get("user_email") for e in events if e.get("user_email") and str(e.get("created_at", ""))[:10] == today}
    counts = {}
    for e in events:
        typ = str(e.get("event_type") or "other")
        counts[typ] = counts.get(typ, 0) + 1
    questions = [e for e in events if e.get("event_type") == "ask" and e.get("question")]
    qfreq = {}
    for e in questions:
        q = str(e.get("question")).strip()
        qfreq[q] = qfreq.get(q, 0) + 1
    popular = sorted(qfreq.items(), key=lambda x: (-x[1], x[0].lower()))[:10]
    activity = []
    for e in events[:100]:
        activity.append({
            "time": e.get("created_at"),
            "event": e.get("event_type"),
            "user": e.get("user_email") or e.get("user_name") or "Unknown",
            "question": e.get("question"),
            "success": bool(e.get("success", True)),
            "metadata": e.get("metadata") or {},
        })
    return {
        "configured": enabled(),
        "days": int(days),
        "total_events": len(events),
        "total_users": len(users),
        "active_today": len(active_today),
        "ai_questions": counts.get("ask", 0),
        "uploads": counts.get("upload", 0),
        "exports": counts.get("export", 0),
        "logins": counts.get("login", 0),
        "errors": counts.get("error", 0),
        "event_counts": counts,
        "popular_questions": [{"question": q, "count": n} for q, n in popular],
        "recent_activity": activity,
    }
