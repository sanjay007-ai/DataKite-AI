from flask import Flask, send_from_directory, request, jsonify, send_file, session, redirect, g
from flask.json.provider import DefaultJSONProvider
import math
import datetime
from werkzeug.utils import secure_filename
import os
import pandas as pd
import numpy as np
import subprocess
import shutil
from pathlib import Path


import re
import json
import zipfile
import io
import base64


from ai_engine import ask_ai, dataset_summary
from csv_reader import load_csv, get_data, set_data
from smart_analytics_engine import answer_question
from comparison_engine import get_comparison_insight
from advanced_comparison_engine import advanced_compare_files, compare_years 
from root_cause_engine import root_cause_analysis, root_cause_years, root_cause_files, load_year_file
from business_recommendation_engine import business_recommendations_years, business_analysis
from dataset_intelligence_engine import dataset_intelligence, profile_dataset
from dynamic_kpi_engine import dynamic_kpis, format_kpi_summary
from statistical_analysis_engine import (
    statistical_analysis,
    format_statistical_summary
)
from trend_analysis_engine import (
    trend_analysis,
    format_trend_summary
)
from anomaly_detection_engine import (
    detect_anomalies,
    format_anomaly_summary
)
from forecasting_engine import (
    forecast_sales,
    format_forecast_summary
)
from advanced_charts_engine import (
    generate_chart_data,
    category_comparison_chart,
    city_comparison_chart,
    payment_method_comparison_chart,
    product_comparison_chart,
    order_status_comparison_chart,
    monthly_sales_comparison_chart,
    growth_analysis_chart,
    profit_analysis_chart,
    customer_analysis_chart
)

from schema_adapter import detect_schema as universal_schema, numeric as universal_numeric, metric as universal_metric, unique_count as universal_unique_count, order_count as universal_order_count, monthly as universal_monthly, grouped as universal_grouped

from auth import init_db, create_user, authenticate, sign_in, current_user, sign_out
from llm_engine import ask_real_ai, llm_enabled
from analyst_engine import analyze as analyst_v2_analyze
from usage_analytics import track_event, usage_summary, is_admin
from upload_pipeline import parse_uploaded_file

from error_handler import (
    safe_execute,
    validate_year,
    format_error,
    ERROR_INVALID_YEAR
)


class SafeJSONProvider(DefaultJSONProvider):
    """JSON provider that converts NaN/Infinity to JSON null.

    Browser JSON.parse() rejects JavaScript NaN/Infinity tokens. Analytics
    engines legitimately use NaN for the first month-over-month growth value,
    so sanitize all API payloads centrally instead of allowing invalid JSON.
    """
    def dumps(self, obj, **kwargs):
        def clean(value):
            if isinstance(value, float) and not math.isfinite(value):
                return None
            if isinstance(value, dict):
                return {str(k): clean(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [clean(v) for v in value]
            try:
                import numpy as np
                if isinstance(value, np.generic):
                    value = value.item()
                    if isinstance(value, float) and not math.isfinite(value):
                        return None
            except Exception:
                pass
            return value
        kwargs.setdefault("allow_nan", False)
        return super().dumps(clean(obj), **kwargs)


app = Flask(__name__)
app.json = SafeJSONProvider(app)
app.secret_key = os.environ.get("DATAKITE_SECRET_KEY", "dev-only-change-this-secret")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1", PERMANENT_SESSION_LIFETIME=60*60*24*30)
init_db()

# Vercel warm-instance dataset cache: keep parsed data server-side and send
# only a small dataset_id on subsequent requests.
_DATASET_CACHE = {}
_DATASET_CACHE_MAX = 4
# Short-lived verified answer cache: repeated questions on the same dataset
# return immediately instead of recalculating the same pandas result.
_ANSWER_CACHE = {}
_ANSWER_CACHE_MAX = 64

def _dataset_cache_key(dataset_id):
    user = current_user() or {}
    return f"{user.get('id', 'anonymous')}:{dataset_id}"

def _cache_dataset(df):
    import uuid, time
    dataset_id = uuid.uuid4().hex
    _DATASET_CACHE[_dataset_cache_key(dataset_id)] = {"data": df, "last_used": time.time()}
    while len(_DATASET_CACHE) > _DATASET_CACHE_MAX:
        oldest = min(_DATASET_CACHE, key=lambda k: _DATASET_CACHE[k]["last_used"])
        _DATASET_CACHE.pop(oldest, None)
    return dataset_id

def _get_cached_dataset(dataset_id):
    if not dataset_id or not isinstance(dataset_id, str):
        return None
    item = _DATASET_CACHE.get(_dataset_cache_key(dataset_id))
    if not item:
        return None
    import time
    item["last_used"] = time.time()
    return item.get("data")

def _answer_cache_key(dataset_id, question):
    return f"{_dataset_cache_key(dataset_id)}:{str(question).strip().lower()}"

def _get_cached_answer(dataset_id, question):
    if not dataset_id or not question:
        return None
    item = _ANSWER_CACHE.get(_answer_cache_key(dataset_id, question))
    if item is None:
        return None
    import time
    item["last_used"] = time.time()
    return item.get("result")

def _cache_answer(dataset_id, question, result):
    if not dataset_id or not question or not isinstance(result, dict):
        return
    import time
    key = _answer_cache_key(dataset_id, question)
    _ANSWER_CACHE[key] = {"result": result, "last_used": time.time()}
    while len(_ANSWER_CACHE) > _ANSWER_CACHE_MAX:
        oldest = min(_ANSWER_CACHE, key=lambda k: _ANSWER_CACHE[k]["last_used"])
        _ANSWER_CACHE.pop(oldest, None)

def _dataset_payload(df):
    """Compact, JSON-safe client dataset for stateless/serverless deployments."""
    if df is None or df.empty:
        return None
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    return {"columns": [str(c) for c in df.columns], "records": records}


def _restore_dataset_payload(payload):
    """Restore a browser-carried dataset safely across serverless instances.

    Accept both the compact dataset object and the full /upload response
    (older frontend builds sent the whole response under ``dataset``).
    """
    if not isinstance(payload, dict):
        return None

    # Backward compatibility: {success, rows, columns, ..., dataset:{...}}
    nested = payload.get("dataset")
    if isinstance(nested, dict) and (
        isinstance(nested.get("records"), list)
        or isinstance(nested.get("columns"), list)
    ):
        payload = nested

    cols = payload.get("columns") or []
    records = payload.get("records") or []

    # Never pass a scalar (for example the upload response's numeric
    # ``columns`` count) to pandas as the DataFrame column index.
    if not isinstance(cols, list) or not cols:
        return None
    if not isinstance(records, list) or not records:
        return None

    try:
        frame = pd.DataFrame(records)
        if frame.empty:
            return None

        # Keep the original upload column order where possible.
        valid_cols = [str(c) for c in cols]
        frame.columns = [str(c) for c in frame.columns]
        ordered = [c for c in valid_cols if c in frame.columns]
        extras = [c for c in frame.columns if c not in ordered]
        frame = frame[ordered + extras]

        set_data(frame)
        return frame
    except Exception as exc:
        print("⚠️ DATASET RESTORE ERROR:", repr(exc))
        return None


def _restore_dataset_from_request():
    """Restore the browser-held dataset once per request.

    ``before_request`` also restores POST datasets for serverless requests.
    Cache the DataFrame on Flask's request-local ``g`` object so the route
    does not rebuild the same pandas DataFrame a second time.
    """
    cached = getattr(g, "_datakite_dataset", None)
    if cached is not None:
        return cached

    payload = None
    if request.method in {"POST", "PUT", "PATCH"}:
        body = request.get_json(silent=True) or {}
        dataset_id = body.get("dataset_id")
        if dataset_id:
            cached = _get_cached_dataset(dataset_id)
            if cached is not None and not cached.empty:
                set_data(cached)
                g._datakite_dataset = cached
                return cached
        payload = body.get("dataset")

    if payload:
        restored = _restore_dataset_payload(payload)
        if restored is not None:
            g._datakite_dataset = restored
            return restored

    current = get_data()
    if current is not None:
        g._datakite_dataset = current
    return current

PUBLIC_PATHS = {"/", "/landing.css", "/landing.js", "/health", "/manifest.json", "/sw.js", "/icon.svg", "/favicon.ico"}

@app.before_request
def require_login():
    if request.path in PUBLIC_PATHS or request.path.startswith("/auth/"):
        return None
    if request.path.startswith("/static/"):
        return None
    if current_user() is None:
        if request.path == "/app":
            return redirect("/")
        return jsonify({"success": False, "error": "Please sign in to use DataKite AI."}), 401
    # Vercel may send the next request to another serverless instance.
    # Restore the browser-carried dataset before any analytics route runs.
    if request.method in {"POST", "PUT", "PATCH"}:
        try:
            restored = _restore_dataset_from_request()
            body = request.get_json(silent=True) or {}
            if body.get("dataset_id") and restored is None:
                return jsonify({
                    "success": False,
                    "error_code": "DATASET_EXPIRED",
                    "error": "The live analysis session expired. Please re-upload the selected files.",
                }), 409
        except Exception as exc:
            print("⚠️ REQUEST DATA RESTORE ERROR:", repr(exc))
    return None

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if os.environ.get("FLASK_DEBUG", "0") != "1":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

@app.errorhandler(413)
def request_too_large(error):
    return jsonify({"error": "Upload is too large. Please reduce the file size or upload fewer files."}), 413

# ==========================================================
# 🔐 PHASE 8.2 — PRODUCTION CONFIG
# ==========================================================

# Max request body size (uploads included). Override with the
# MAX_UPLOAD_MB environment variable in production if needed.
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# Max pages read from an uploaded PDF, to avoid huge/adversarial
# files stalling the server. Used by file_reader.read_pdf().
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "200"))

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")
UPLOAD_FOLDER = (
    "/tmp/datakite_uploads"
    if os.environ.get("VERCEL") == "1"
    else os.environ.get(
        "DATAKITE_UPLOAD_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
    )
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ==========================================================
# 🧹 TEMP-FILE CLEANUP
# ==========================================================
# Uploaded files and generated conversions/reports accumulate in
# UPLOAD_FOLDER. Anything older than UPLOAD_MAX_AGE_HOURS is
# removed on startup and every CLEANUP_INTERVAL_MINUTES after
# that, so disk usage doesn't grow unbounded in production.

UPLOAD_MAX_AGE_HOURS = float(
    os.environ.get("UPLOAD_MAX_AGE_HOURS", "24")
)
CLEANUP_INTERVAL_MINUTES = float(
    os.environ.get("CLEANUP_INTERVAL_MINUTES", "60")
)


def cleanup_old_uploads():

    import time

    cutoff = time.time() - (UPLOAD_MAX_AGE_HOURS * 3600)

    # Both the uploads folder and the report_charts scratch folder
    # (used by create_report_charts for PDF report generation)
    # accumulate temp files that need periodic cleanup.
    folders = [
        UPLOAD_FOLDER,
        os.path.join(os.path.dirname(__file__), "report_charts"),
    ]

    for folder in folders:

        try:

            for name in os.listdir(folder):

                path = os.path.join(folder, name)

                try:

                    if (
                        os.path.isfile(path)
                        and os.path.getmtime(path) < cutoff
                    ):

                        os.remove(path)

                        print("🧹 Removed old temp file:", path)

                except OSError as error:

                    print("⚠️ Cleanup skipped for", path, ":", error)

        except FileNotFoundError:
            pass


def start_cleanup_scheduler():

    import threading

    def loop():

        while True:

            cleanup_old_uploads()

            threading.Event().wait(
                CLEANUP_INTERVAL_MINUTES * 60
            )

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


cleanup_old_uploads()
# Never keep a background scheduler alive inside a Vercel serverless instance.
# The instance can be frozen/reused unpredictably; cleanup at request/startup
# is enough and avoids an unnecessary permanent thread.
if os.environ.get("VERCEL") != "1":
    start_cleanup_scheduler()


@app.errorhandler(413)
def handle_file_too_large(error):
    return jsonify({
        "error": (
            f"File too large. Maximum allowed size is "
            f"{MAX_UPLOAD_MB} MB."
        )
    }), 413


@app.errorhandler(400)
def handle_bad_request(error):
    return jsonify({
        "error": "Bad request. Please check your input and try again."
    }), 400


@app.errorhandler(404)
def handle_not_found(error):
    return jsonify({
        "error": "The requested resource was not found."
    }), 404


@app.errorhandler(500)
def handle_server_error(error):
    print("❌ UNHANDLED SERVER ERROR:", repr(error))
    return jsonify({
        "error": "An unexpected server error occurred."
    }), 500


@app.route("/")
def home():
    return send_from_directory(FRONTEND, "index.html")

@app.route("/app")
def app_workspace():
    return send_from_directory(FRONTEND, "app.html")

@app.route("/auth/register", methods=["POST"])
def auth_register():
    payload = request.get_json(silent=True) or {}
    user, error = create_user(payload.get("name"), payload.get("email"), payload.get("password"))
    if error:
        return jsonify({"success": False, "error": error}), 400
    sign_in(user)
    track_event("register", user=user)
    return jsonify({"success": True, "user": user})

@app.route("/auth/login", methods=["POST"])
def auth_login():
    payload = request.get_json(silent=True) or {}
    user = authenticate(payload.get("email"), payload.get("password"))
    if not user:
        return jsonify({"success": False, "error": "Incorrect email or password."}), 401
    sign_in(user)
    track_event("login", user=user)
    return jsonify({"success": True, "user": user})

@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    user = current_user()
    if user:
        track_event("logout", user=user)
    sign_out()
    return jsonify({"success": True})

@app.route("/auth/me")
def auth_me():
    user = current_user()
    return jsonify({"authenticated": bool(user), "user": user, "is_admin": bool(is_admin(user))})

@app.route("/admin")
def admin_workspace():
    user = current_user()
    if not is_admin(user):
        return jsonify({"success": False, "error": "Owner access only."}), 403
    return send_from_directory(FRONTEND, "admin.html")

@app.route("/admin/usage/summary")
def admin_usage_summary():
    user = current_user()
    if not is_admin(user):
        return jsonify({"success": False, "error": "Owner access only."}), 403
    return jsonify({"success": True, "usage": usage_summary(30)})

@app.route("/landing.css")
def landing_css():
    return send_from_directory(FRONTEND, "landing.css")

@app.route("/landing.js")
def landing_js():
    return send_from_directory(FRONTEND, "landing.js")

@app.route("/style.css")
def css():
    return send_from_directory(FRONTEND, "style.css")

@app.route("/script.js")
def js():
    return send_from_directory(FRONTEND, "script.js")

@app.route("/manifest.json")
def manifest():
    return send_from_directory(FRONTEND, "manifest.json", mimetype="application/manifest+json")

@app.route("/sw.js")
def service_worker():
    response = send_from_directory(FRONTEND, "sw.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response

@app.route("/icon.svg")
def icon():
    return send_from_directory(FRONTEND, "icon.svg", mimetype="image/svg+xml")

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(FRONTEND, "icon.svg", mimetype="image/svg+xml")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "DataKite AI"})
# ==========================================================
# 📊 PHASE 6.2 — DYNAMIC KPI / ANALYTICS
# ==========================================================

def _fast_dashboard_payload(data):
    """Compute the complete first dashboard in one lightweight pandas pass.

    This intentionally avoids the larger analytics engines during initial
    dashboard rendering. Heavy AI/statistical features remain available on
    demand, while upload -> dashboard stays fast and deterministic.
    """
    if data is None or data.empty:
        return {"kpis": {}, "charts": {}, "health": {"score": 0, "label": "Needs data", "components": [], "summary": "No data loaded."}}
    from schema_adapter import detect_schema, numeric, monthly, grouped, unique_count, order_count
    schema = detect_schema(data)
    sales_col, profit_col, qty_col = schema.get("sales"), schema.get("profit"), schema.get("quantity")
    sales = numeric(data, sales_col) if sales_col else pd.Series(0.0, index=data.index)
    profit = numeric(data, profit_col) if profit_col else pd.Series(0.0, index=data.index)
    qty = numeric(data, qty_col) if qty_col else pd.Series(0.0, index=data.index)
    orders = order_count(data, schema)
    total_sales = float(sales.sum()); total_profit = float(profit.sum()); total_qty = float(qty.sum())
    customers = unique_count(data, schema.get("customer")); products = unique_count(data, schema.get("product"))
    kpis = {
        "total_sales": total_sales,
        "total_profit": total_profit,
        "total_orders": int(orders),
        "unique_customers": int(customers),
        "unique_products": int(products),
        "total_quantity": total_qty,
        "average_order_value": (total_sales / orders) if orders else 0.0,
        "profit_margin": (total_profit / total_sales * 100) if total_sales else 0.0,
    }
    charts = {}
    m = monthly(data, schema, "sales")
    if not m.empty:
        m = m.tail(24)
        charts["sales"] = {"labels": m["period"].tolist(), "values": [float(x) for x in m["sales"].tolist()], "field": sales_col, "date_field": schema.get("date")}
    else:
        charts["sales"] = {"labels": [], "values": [], "field": sales_col, "date_field": schema.get("date")}
    for key, value_kind, limit in (("category", "sales", 10), ("city", "sales", 10), ("product", "quantity", 5)):
        result = grouped(data, schema.get(key), schema.get(value_kind), n=limit)
        charts[key] = {"labels": result["label"].tolist(), "values": [float(x) for x in result["value"].tolist()], "field": schema.get(key), "value_field": schema.get(value_kind)}
    status_col = schema.get("status")
    if status_col and status_col in data.columns:
        st = data[status_col].astype(str).replace({"nan": "Unknown"}).value_counts().head(10)
        charts["status"] = {"labels": st.index.tolist(), "values": [int(x) for x in st.tolist()], "field": status_col}
    else:
        charts["status"] = {"labels": [], "values": [], "message": "No status field detected."}
    # Use the universal explainable health engine so the dashboard returns
    # both the overall score and the five category scores/reasons.
    # Keep a tiny fallback so dashboard loading never fails just because a
    # health sub-calculation cannot be produced for an unusual dataset.
    try:
        from business_health_engine import business_health
        health = business_health(data)
    except Exception as health_exc:
        print("⚠️ BUSINESS HEALTH ENGINE FALLBACK:", repr(health_exc))
        completeness = float(data.notna().mean().mean() * 100) if len(data.columns) else 0
        margin_score = max(0, min(100, 55 + (total_profit / total_sales * 100 * 3 if total_sales else 0)))
        trend_score = 70
        if len(m) >= 2 and float(m.iloc[-2]["sales"]) != 0:
            growth = (float(m.iloc[-1]["sales"]) / float(m.iloc[-2]["sales"]) - 1) * 100
            trend_score = max(0, min(100, 65 + growth * 2))
        health_score = int(round(max(0, min(100, (margin_score + trend_score + max(55, min(100, completeness))) / 3))))
        label = "Excellent" if health_score >= 85 else "Healthy" if health_score >= 70 else "Watch" if health_score >= 55 else "Needs attention"
        health = {"score": health_score, "label": label, "components": [], "summary": f"Business Health is {health_score}/100 — {label.lower()}."}
    return {"kpis": kpis, "charts": charts, "health": health}


@app.route("/analytics/bootstrap", methods=["POST"])
def analytics_bootstrap():
    try:
        data = _restore_dataset_from_request()
        if data is None or data.empty:
            return jsonify({"success": False, "error": "Please upload a file first."}), 400
        cache_item = _DATASET_CACHE.get(_dataset_cache_key(session.get("dataset_id"))) if session.get("dataset_id") else None
        if cache_item and cache_item.get("dashboard") is not None:
            result = cache_item["dashboard"]
        else:
            result = _fast_dashboard_payload(data)
            if cache_item is not None:
                cache_item["dashboard"] = result
        return jsonify({"success": True, **result})
    except Exception as exc:
        print("❌ ANALYTICS BOOTSTRAP ERROR:", repr(exc))
        return jsonify({"success": False, "error": "Could not prepare the dashboard."}), 500


def _universal_chart_data(data, group_kind, value_kind, limit=10, monthly_mode=False):
    schema = universal_schema(data)
    if monthly_mode:
        result = universal_monthly(data, schema, value_kind)
        if result.empty: return {"labels": [], "values": [], "field": schema.get(value_kind), "date_field": schema.get("date")}
        result = result.tail(limit)
        return {"labels": result["period"].tolist(), "values": [float(x) for x in result[value_kind].tolist()], "field": schema.get(value_kind), "date_field": schema.get("date")}
    group_col, value_col = schema.get(group_kind), schema.get(value_kind)
    result = universal_grouped(data, group_col, value_col, n=limit)
    return {"labels": result["label"].tolist(), "values": [float(x) for x in result["value"].tolist()], "field": group_col, "value_field": value_col}


def _status_chart_data(data):
    schema = universal_schema(data); col = schema.get("status")
    if not col: return {"labels": [], "values": [], "message": "No status field detected."}
    result = data[col].astype(str).value_counts().head(10)
    return {"labels": result.index.tolist(), "values": result.values.tolist(), "field": col}

@app.route("/analytics/kpis", methods=["GET", "POST"])
def dynamic_kpi_analytics():

    try:
        data = get_data()

        if data is None or data.empty:
            return jsonify({
                "success": False,
                "error": "Please upload a CSV or Excel file first."
            }), 400

        # Run Phase 6.2 Dynamic KPI Engine
        result = dynamic_kpis(data)

        return jsonify({
            "success": True,
            "message": "Dynamic KPI analysis completed.",
            "kpis": result.get("kpis", {}),
            "metric_columns": result.get(
                "metric_columns", []
            ),
            "dimension_columns": result.get(
                "dimension_columns", []
            ),
            "date_columns": result.get(
                "date_columns", []
            ),
            "detected_metrics": result.get(
                "detected_metrics", {}
            ),
            "summary": format_kpi_summary(result)
        })

    except Exception as e:

        print(
            "❌ PHASE 6.2 KPI ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500    
@app.route("/ask", methods=["POST"])
def ask():

    try:

        data = request.get_json(silent=True) or {}

        question = str(
            data.get("question", "")
        ).strip()

        if not question:

            return jsonify({
                "answer": "Please enter a question."
            })

        print("Question received:", repr(question))

        # ==================================================
        # 🧠 AI ANALYST V2 — deterministic-first reasoning
        # Calculate with pandas first, validate the result, then explain it.
        # Conversation history is kept per signed user session.
        # ==================================================
        smart_data = get_data()
        if smart_data is not None and not smart_data.empty and not any(token in question.lower() for token in ("generate word", "create word", "generate docx", "create docx", "generate pdf", "create pdf", "generate ppt", "create ppt", "generate powerpoint", "export excel")):
            try:
                dataset_id = session.get("dataset_id")
                cached_result = _get_cached_answer(dataset_id, question)
                if cached_result is not None:
                    track_event("ask", user=current_user(), question=question, success=True, cached=True, intent=cached_result.get("intent"))
                    return jsonify(cached_result)
                history = session.get("analyst_history", [])
                result = analyst_v2_analyze(smart_data, question, history=history)
                if result.get("ok"):
                    _cache_answer(dataset_id, question, result)
                    # Save compact verified context for follow-up questions without
                    # bloating the signed session cookie.
                    history = (history + [{
                        "question": question,
                        "intent": result.get("intent"),
                        "answer": result.get("answer", "")[:900],
                        "calculation": result.get("calculation", {})
                    }])[-8:]
                    session["analyst_history"] = history
                    session.modified = True
                    track_event("ask", user=current_user(), question=question, success=True, cached=False, intent=result.get("intent"))
                    return jsonify(result)
            except Exception as analyst_error:
                print("⚠️ Analyst V2 fallback:", repr(analyst_error))

        # Real LLM is now a narrative fallback, never the source of numeric truth.
        if llm_enabled() and not any(token in question.lower() for token in ("generate word", "create word", "generate docx", "create docx", "generate pdf", "create pdf", "generate ppt", "create ppt", "generate powerpoint", "export excel")):
            real_answer = ask_real_ai(question, smart_data)
            if real_answer:
                track_event("ask", user=current_user(), question=question, success=True, ai_mode="gemini-free-tier")
                return jsonify({"answer": real_answer, "ai_mode": "gemini-free-tier"})

        # ==================================================
        # 📝 GENERATE WORD REPORT
        # ==================================================

        if (
            "generate word" in question.lower()
            or "create word" in question.lower()
            or "generate docx" in question.lower()
            or "create docx" in question.lower()
        ):

            word_data = get_data()

            if word_data is None or word_data.empty:
                return jsonify({
                    "answer": "❌ Please upload a CSV or Excel file first."
                })

            return jsonify({
                "answer": "📝 Professional Word Report",
                "word": "/word/download"
            })

        # ==================================================
        # 📕 GENERATE PDF REPORT
        # ==================================================

        if (
            "generate pdf" in question.lower()
            or "create pdf" in question.lower()
        ):

            csv_data = get_data()

            if csv_data is None:

                return jsonify({
                    "answer": "❌ Please upload a CSV file first."
                })

            return jsonify({
                "answer": "📕 Professional PDF Report",
                "pdf": "/pdf/download"
            })
        # ==================================================
        # 📊 SHOW CHARTS AND SHOW TABLE
        # ==================================================

        q = question.lower()

        # ==================================================
        # 🧠 FINAL SMART AI ORCHESTRATOR
        # Handles short, natural, long and follow-up business questions
        # before legacy keyword routing. Existing engines remain available.
        # ==================================================
        smart_data = get_data()
        if smart_data is not None and not smart_data.empty:
            try:
                smart_result = answer_question(
                    smart_data,
                    question,
                    history=session.get("analyst_history", [])
                )
                if smart_result and smart_result.get("answer"):
                    # Smart router owns ordinary analytics questions.
                    # Keep explicit UI commands below for dashboard/table/chart controls.
                    smart_intent = smart_result.get("intent")
                    ui_command = (
                        "only chart" in q or "show charts" in q or "show chart" in q
                        or "only table" in q or "show table" in q or "dashboard" in q
                        or "full report" in q or "show everything" in q or "show me everything" in q
                    )
                    if not ui_command:
                        print("🧠 Smart AI Answer:", repr(smart_result["answer"]))
                        return jsonify(smart_result)
            except Exception as smart_error:
                print("⚠️ Smart AI fallback to existing engines:", repr(smart_error))

        if "only chart" in q or "show charts" in q or "show chart" in q:

            csv_data = get_data()

            if csv_data is None:
                return jsonify({
                    "answer": "❌ Please upload a CSV file first."
                })

            return jsonify({
                "answer": "📊 Business Analytics Charts",
                "show_charts": True
            })

        if (
            "only table" in q
            or "show table" in q
            or "dashboard" in q
            or "full report" in q
            or "show everything" in q
            or "show me everything" in q
        ):

            csv_data = get_data()

            if csv_data is None:
                return jsonify({
                    "answer": "❌ Please upload a CSV file first."
                })

            return jsonify({
                "answer": "📋 Here's your full dashboard — KPIs, charts, insights, and recommendations.",
                "show_table": True
            })

        # ==================================================
        # 🤖 NORMAL AI QUESTION
        # ==================================================
        
        # ==================================================
        # 🔥 PHASE 5.4.2 — ADVANCED YEAR COMPARISON
        # ==================================================

        if q.lower().startswith("compare "):

            year_match = re.search(
                r"compare\s+(20\d{2})\s+(?:and|vs|versus)\s+(20\d{2})",
                q,
                re.IGNORECASE
            )

            if year_match:

                year1 = year_match.group(1)
                year2 = year_match.group(2)

                result = safe_execute(
                    advanced_compare_files,
                    year1,
                    year2,
                    engine="comparison"
                )

                if result["success"]:

                    answer = result["result"]

                    print(
                        "Advanced Comparison Answer:",
                        repr(answer)
                    )

                    return jsonify({
                        "answer": str(answer)
                    })

                return jsonify({
                    "answer": result["error"]
                })
        # ==================================================
        # 🔥 PHASE 5.4 — GENERAL COMPARISON
        # ==================================================

        
        comparison_answer = get_comparison_insight(question)

        if comparison_answer:

            print(
                "Comparison Answer:",
                repr(comparison_answer)
            )

            return jsonify({
                "answer": comparison_answer
            })
        # ============================================================
        # 🔥 PHASE 5.5 — ROOT CAUSE ANALYSIS
        # ============================================================

        q_lower = q.lower().strip()

        root_cause_request = (
            "root cause" in q_lower
            or "why did" in q_lower
            or "why has" in q_lower
            or "why has" in q_lower
            or "what caused" in q_lower
            or "what is causing" in q_lower
            or "reason for" in q_lower
            or "sales increase" in q_lower
        )

        if root_cause_request:

            year_match = re.search(
                r"(20\d{2}).*?(20\d{2})",
                q_lower,
                re.IGNORECASE
            )

            if year_match:

                year1 = year_match.group(1)
                year2 = year_match.group(2)

            else:

                year1 = "2024"
                year2 = "2025"

            result = safe_execute(
                root_cause_years,
                year1,
                year2,
                engine="root cause"
            )

            if result["success"]:

                root_answer = result["result"]

                print(
                    "Root Cause Answer:",
                    repr(root_answer)
                )

                return jsonify({
                    "answer": str(root_answer)
                })

            return jsonify({
                "answer": result["error"]
            })

        # ============================================================
        # 🔥 PHASE 5.6 — BUSINESS RECOMMENDATIONS
        # ============================================================

        recommendation_patterns = [
            "recommend",
            "recommendation",
            "suggestion",
            "suggest",
            "how can i improve",
            "how can we improve",
            "how to improve",
            "what should i do",
            "what should we do",
            "what should the business improve",
            "action plan",
            "action items"
        ]

        recommendation_request = any(
            pattern in q_lower
            for pattern in recommendation_patterns
        )

        if recommendation_request:

            year_match = re.search(
                r"(20\d{2}).*?(20\d{2})",
                q_lower,
                re.IGNORECASE
            )

            if year_match:

                rec_year1 = year_match.group(1)
                rec_year2 = year_match.group(2)

            else:

                rec_year1 = "2024"
                rec_year2 = "2025"

            result = safe_execute(
                business_recommendations_years,
                rec_year1,
                rec_year2,
                engine="recommendation"
            )

            if result["success"]:

                recommendation_answer = result["result"]

                print(
                    "Recommendation Answer:",
                    repr(recommendation_answer)
                )

                return jsonify({
                    "answer": str(recommendation_answer)
                })

            return jsonify({
                "answer": result["error"]
            })

        # ============================================================
        # 📊 PHASE 6.2 — DYNAMIC KPI / ANALYTICS
        # ============================================================

        q_lower = question.lower().strip()

        kpi_request = (
            "kpi" in q_lower
            or "key performance" in q_lower
            or "key metrics" in q_lower
            or "business metrics" in q_lower
            or "show metrics" in q_lower
            or "show kpis" in q_lower
            or "show me kpis" in q_lower
            or "kpi summary" in q_lower
            or "key kpis" in q_lower
            or "overall performance" in q_lower
            or "performance summary" in q_lower

            # 6.2.5 individual KPI questions
            or "average order value" in q_lower
            or "average order" in q_lower
            or "aov" in q_lower
            or "total profit" in q_lower
            or "profit made" in q_lower
            or "how much profit" in q_lower
            or "average profit" in q_lower
            or "profit margin" in q_lower
            or "unique customers" in q_lower
            or "number of customers" in q_lower
            or "how many customers" in q_lower
            or "unique orders" in q_lower
            or "number of orders" in q_lower
            or "how many orders" in q_lower
            or "total quantity" in q_lower
            or "quantity sold" in q_lower
            or "unique products" in q_lower
            or "number of products" in q_lower
            or "how many products" in q_lower
            or "minimum sale" in q_lower
            or "lowest sale" in q_lower
            or "smallest sale" in q_lower
            or "maximum sale" in q_lower
            or "highest sale" in q_lower
            or "largest sale" in q_lower
        )

        if kpi_request:

            try:

                current_data = get_data()

                if current_data is None or current_data.empty:
                    return jsonify({
                        "answer": "❌ Please upload a CSV or Excel file first."
                    })

                # --------------------------------------------------------
                # 6.2.5 — INDIVIDUAL KPI QUESTIONS
                # --------------------------------------------------------

                kpi_result = dynamic_kpis(current_data)
                kpis = kpi_result.get("kpis", {})

                if kpi_result.get("error"):
                    return jsonify({
                        "answer": f"❌ KPI analysis error: "
                                  f"{kpi_result['error']}"
                    })

                def kpi_value(key, label, prefix="", suffix=""):

                    if key not in kpis:
                        return None

                    return jsonify({
                        "answer": (
                            f"📊 {label}: "
                            f"{prefix}{kpis[key]:,.2f}{suffix}"
                        )
                    })

                # Average Order Value
                if (
                    "average order value" in q_lower
                    or "average order" in q_lower
                    or "aov" in q_lower
                ):
                    response = kpi_value(
                        "average_order_value",
                        "Average Order Value",
                        "₹"
                    )

                    if response:
                        return response

                # Total Profit
                if (
                    "total profit" in q_lower
                    or "profit made" in q_lower
                    or "how much profit" in q_lower
                ):
                    response = kpi_value(
                        "total_profit",
                        "Total Profit",
                        "₹"
                    )

                    if response:
                        return response

                # Average Profit
                if "average profit" in q_lower:
                    response = kpi_value(
                        "average_profit",
                        "Average Profit",
                        "₹"
                    )

                    if response:
                        return response

                # Profit Margin
                if (
                    "profit margin" in q_lower
                    or "margin" in q_lower
                ):
                    response = kpi_value(
                        "profit_margin",
                        "Profit Margin",
                        "",
                        "%"
                    )

                    if response:
                        return response

                # Unique Customers
                if (
                    "unique customers" in q_lower
                    or "number of customers" in q_lower
                    or "how many customers" in q_lower
                ):
                    response = kpi_value(
                        "unique_customers",
                        "Unique Customers"
                    )

                    if response:
                        return response

                # Unique Orders
                if (
                    "unique orders" in q_lower
                    or "number of orders" in q_lower
                    or "how many orders" in q_lower
                ):
                    response = kpi_value(
                        "unique_orders",
                        "Unique Orders"
                    )

                    if response:
                        return response

                # Total Quantity
                if (
                    "total quantity" in q_lower
                    or "quantity sold" in q_lower
                ):
                    response = kpi_value(
                        "total_quantity",
                        "Total Quantity"
                    )

                    if response:
                        return response

                # Unique Products
                if (
                    "unique products" in q_lower
                    or "number of products" in q_lower
                    or "how many products" in q_lower
                ):
                    response = kpi_value(
                        "unique_products",
                        "Unique Products"
                    )

                    if response:
                        return response

                # Minimum Sale
                if (
                    "minimum sale" in q_lower
                    or "lowest sale" in q_lower
                    or "smallest sale" in q_lower
                ):
                    response = kpi_value(
                        "minimum_sales",
                        "Minimum Sale",
                        "₹"
                    )

                    if response:
                        return response

                # Maximum Sale
                if (
                    "maximum sale" in q_lower
                    or "highest sale" in q_lower
                    or "largest sale" in q_lower
                ):
                    response = kpi_value(
                        "maximum_sales",
                        "Maximum Sale",
                        "₹"
                    )

                    if response:
                        return response

                # --------------------------------------------------------
                # 📊 FULL KPI SUMMARY
                # --------------------------------------------------------

                kpi_answer = format_kpi_summary(kpi_result)

                print(
                    "📊 Phase 6.2 KPI Answer:",
                    repr(kpi_answer)
                )

                return jsonify({
                    "answer": kpi_answer,
                    "kpis": kpi_result.get("kpis", {}),
                    "detected_metrics": kpi_result.get(
                        "detected_metrics",
                        {}
                    )
                })

            except Exception as e:

                print(
                    "⚠️ Phase 6.2 Dynamic KPI Engine:",
                    repr(e)
                )

                return jsonify({
                    "answer":
                        "❌ I could not calculate the dynamic KPIs."
                })
        # ============================================================
        # 📊 PHASE 6.3 — STATISTICAL ANALYSIS
        # ============================================================

        statistical_request = (
            "statistical analysis" in q_lower
            or "statistics" in q_lower
            or "statistical" in q_lower
            or "standard deviation" in q_lower
            or "variance" in q_lower
            or "median" in q_lower
            or "mean" in q_lower
            or "quartile" in q_lower
            or "iqr" in q_lower
            or "skewness" in q_lower
            or "correlation" in q_lower
        )

        if statistical_request:

            try:

                current_data = get_data()

                if current_data is None or current_data.empty:
                    return jsonify({
                        "answer": "❌ Please upload a CSV or Excel file first."
                    })

                # Run Phase 6.3 Statistical Engine
                statistical_result = statistical_analysis(
                    current_data
                )

                if statistical_result.get("error"):
                    return jsonify({
                        "answer": (
                            "❌ Statistical analysis error: "
                            f"{statistical_result['error']}"
                        )
                    })

                statistical_answer = format_statistical_summary(
                    statistical_result
                )

                print(
                    "📊 Phase 6.3 Statistical Answer:",
                    repr(statistical_answer)
                )

                return jsonify({
                    "answer": statistical_answer,
                    "statistics": statistical_result.get(
                        "statistics",
                        {}
                    ),
                    "correlations": statistical_result.get(
                        "correlations",
                        {}
                    )
                })

            except Exception as e:

                print(
                    "⚠️ Phase 6.3 Statistical Analysis:",
                    repr(e)
                )

                return jsonify({
                    "answer":
                        "❌ I could not perform statistical analysis."
                })
        # ============================================================
        # 📈 PHASE 6.4 — TREND ANALYSIS
        # ============================================================

        trend_request = (
            "trend analysis" in q_lower
            or "sales trend" in q_lower
            or "sales growth" in q_lower
            or "growth trend" in q_lower
            or "monthly trend" in q_lower
            or "monthly sales" in q_lower
            or "sales increasing" in q_lower
            or "sales decreasing" in q_lower
            or "sales growing" in q_lower
            or "sales declining" in q_lower
            or "highest sales month" in q_lower
            or "lowest sales month" in q_lower
            or "best month" in q_lower
            or "worst month" in q_lower
            or "performance trend" in q_lower
            
        )

        if trend_request:

            try:

                current_data = get_data()

                if current_data is None or current_data.empty:
                    return jsonify({
                        "answer": "❌ Please upload a CSV or Excel file first."
                    })

                # Run Phase 6.4 Trend Engine
                trend_result = trend_analysis(
                    current_data
                )

                if trend_result.get("error"):
                    return jsonify({
                        "answer": (
                            "❌ Trend analysis error: "
                            f"{trend_result['error']}"
                        )
                    })

                trend_answer = format_trend_summary(
                    trend_result
                )

                print(
                    "📈 Phase 6.4 Trend Answer:",
                    repr(trend_answer)
                )

                return jsonify({
                    "answer": trend_answer,
                    "trend": trend_result
                })

            except Exception as e:

                print(
                    "⚠️ Phase 6.4 Trend Analysis:",
                    repr(e)
                )

                return jsonify({
                    "answer":
                        "❌ I could not perform trend analysis."
                })
        # ============================================================
        # 🚨 PHASE 6.5 — ANOMALY DETECTION
        # ============================================================

        anomaly_request = (
            "anomaly" in q_lower
            or "anomalies" in q_lower
            or "outlier" in q_lower
            or "outliers" in q_lower
            or "unusual sales" in q_lower
            or "unusual values" in q_lower
            or "abnormal sales" in q_lower
            or "abnormal values" in q_lower
            or "detect anomalies" in q_lower
            or "find anomalies" in q_lower
            or "detect outliers" in q_lower
            or "find outliers" in q_lower
            or "unusual transactions" in q_lower
        )

        if anomaly_request:

            try:

                current_data = get_data()

                if current_data is None or current_data.empty:
                    return jsonify({
                        "answer": "❌ Please upload a CSV or Excel file first."
                    })

                # Run Phase 6.5 Anomaly Engine
                anomaly_result = detect_anomalies(
                    current_data
                )

                if anomaly_result.get("error"):
                    return jsonify({
                        "answer": (
                            "❌ Anomaly detection error: "
                            f"{anomaly_result['error']}"
                        )
                    })

                anomaly_answer = format_anomaly_summary(
                    anomaly_result
                )

                print(
                    "🚨 Phase 6.5 Anomaly Answer:",
                    repr(anomaly_answer)
                )

                return jsonify({
                    "answer": anomaly_answer,
                    "anomalies": anomaly_result.get(
                        "anomalies",
                        {}
                    )
                })

            except Exception as e:

                print(
                    "⚠️ PHASE 6.5 ERROR:",
                    repr(e)
                )

                return jsonify({
                    "answer": (
                        "❌ Anomaly detection error: "
                        f"{type(e).__name__}: {str(e)}"
                    )
                })
        # ============================================================
        # 🔮 PHASE 6.6 — FORECASTING
        # ============================================================

        forecast_request = (
            "forecast" in q_lower
            or "forecasting" in q_lower
            or "predict sales" in q_lower
            or "predict revenue" in q_lower
            or "future sales" in q_lower
            or "future revenue" in q_lower
            or "sales prediction" in q_lower
            or "sales forecast" in q_lower
            or "revenue forecast" in q_lower
            or "expected sales" in q_lower
            or "what will sales look like next month" in q_lower
            or "what will revenue look like next month" in q_lower
            or "next month sales" in q_lower
            or "next month revenue" in q_lower
        )

        if forecast_request:

            try:

                current_data = get_data()

                if current_data is None or current_data.empty:
                    return jsonify({
                        "answer":
                            "❌ Please upload a CSV or Excel file first."
                    })

                # Run Phase 6.6 Forecast Engine
                forecast_result = forecast_sales(
                    current_data,
                    periods=6
                )

                if forecast_result.get("error"):
                    return jsonify({
                        "answer": (
                            "❌ Forecasting error: "
                            f"{forecast_result['error']}"
                        )
                    })

                forecast_answer = format_forecast_summary(
                    forecast_result
                )

                print(
                    "🔮 Phase 6.6 Forecast Answer:",
                    repr(forecast_answer)
                )

                return jsonify({
                    "answer": forecast_answer,
                    "forecast": forecast_result.get(
                        "forecast",
                        []
                    ),
                    "trend": forecast_result.get(
                        "trend"
                    ),
                    "forecast_growth":
                        forecast_result.get(
                            "forecast_growth"
                        )
                    })

            except Exception as e:

                print(
                    "⚠️ PHASE 6.6 FORECAST ERROR:",
                    repr(e)
                )

                return jsonify({
                    "answer": (
                        "❌ Forecasting error: "
                        f"{type(e).__name__}: {str(e)}"
                    )
                })
        # ============================================================
        # 📊 PHASE 6.7.2 — ADVANCED CHART REQUESTS
        # ============================================================

        chart_request = (
            "show chart" in q_lower
            or "create chart" in q_lower  
            or "make chart" in q_lower
            or "generate chart" in q_lower
            or "sales chart" in q_lower
            or "revenue chart" in q_lower
            or "show sales by category" in q_lower
            or "sales by category" in q_lower
            or "compare categories" in q_lower
            or "category comparison" in q_lower
            or "compare category" in q_lower
            or "sales by city" in q_lower
            or "revenue by city" in q_lower
            or "sales by payment method" in q_lower
            or "revenue by payment method" in q_lower
            or "compare payment methods" in q_lower
            or "payment method comparison" in q_lower
            or "compare payments" in q_lower
            or "sales by product" in q_lower
            or "revenue by product" in q_lower
            or "compare products" in q_lower
            or "product comparison" in q_lower
            or "top products" in q_lower
            or "show products" in q_lower
            or "sales by order status" in q_lower
            or "revenue by order status" in q_lower
            or "compare order status" in q_lower
            or "compare order statuses" in q_lower
            or "order status comparison" in q_lower 
            or "show order status" in q_lower
            or "sales by month" in q_lower
            or "revenue by month" in q_lower
            or "monthly sales" in q_lower
            or "monthly revenue" in q_lower
            or "monthly sales comparison" in q_lower
            or "compare months" in q_lower
            or "sales trend by month" in q_lower
            or "growth analysis" in q_lower
            or "sales growth" in q_lower
            or "revenue growth" in q_lower
            or "growth chart" in q_lower
            or "growth trend" in q_lower
            or "show growth" in q_lower
            or "profit analysis" in q_lower
            or "profit by month" in q_lower
            or "monthly profit" in q_lower
            or "profit trend" in q_lower
            or "show profit" in q_lower
            or "customer analysis" in q_lower
            or "sales by customer" in q_lower
            or "revenue by customer" in q_lower
            or "customer comparison" in q_lower 
            or "compare customers" in q_lower
            or "top customers" in q_lower
            or "top customer" in q_lower
        )  
        
        if chart_request:

            try:

                current_data = get_data()

                if current_data is None or current_data.empty:
                    return jsonify({
                        "answer": "❌ Please upload a CSV or Excel file first."
                    })

                # --------------------------------------------------------
                # CATEGORY COMPARISON
                # --------------------------------------------------------

                if (
                    "category" in q_lower
                    or "categories" in q_lower
                ):

                    chart_result = category_comparison_chart(
                        current_data
                    )
                # --------------------------------------------------------
                # CITY COMPARISON — PHASE 6.7.3
                # --------------------------------------------------------

                elif (
                    "city" in q_lower
                    or "cities" in q_lower
                ):

                    chart_result = city_comparison_chart(
                        current_data
                    )
                # --------------------------------------------------------
                # PAYMENT METHOD — 6.7.4
                # --------------------------------------------------------

                elif (
                    "payment method" in q_lower
                    or "payment methods" in q_lower
                    or "payment" in q_lower
                ):

                    chart_result = payment_method_comparison_chart(
                        current_data
                    )
                # --------------------------------------------------------
                # PRODUCT COMPARISON — 6.7.5
                # --------------------------------------------------------

                elif (
                    "product" in q_lower
                    or "products" in q_lower
                ):

                    chart_result = product_comparison_chart(
                        current_data
                    )
                # --------------------------------------------------------
                # ORDER STATUS — 6.7.6
                # --------------------------------------------------------

                elif (
                    "order status" in q_lower
                    or "order statuses" in q_lower
                    or "status comparison" in q_lower
                    or "compare status" in q_lower
                ):

                    chart_result = order_status_comparison_chart(
                        current_data
                    )                     
                # --------------------------------------------------------
                # MONTHLY SALES — 6.7.7
                # --------------------------------------------------------

                elif (
                    "sales by month" in q_lower
                    or "revenue by month" in q_lower
                    or "monthly sales" in q_lower
                    or "monthly revenue" in q_lower
                    or "monthly sales comparison" in q_lower
                    or "compare months" in q_lower
                    or "sales trend by month" in q_lower
                ):

                    chart_result = monthly_sales_comparison_chart(
                        current_data
                    )      
                # --------------------------------------------------------
                # GROWTH ANALYSIS — 6.7.8
                # --------------------------------------------------------

                elif (
                    "growth analysis" in q_lower
                    or "sales growth" in q_lower
                    or "revenue growth" in q_lower
                    or "growth chart" in q_lower
                    or "growth trend" in q_lower
                    or "show growth" in q_lower
                ):

                    chart_result = growth_analysis_chart(
                        current_data
                    )
                # --------------------------------------------------------
                # PROFIT ANALYSIS — 6.7.9
                # --------------------------------------------------------

                elif (
                    "profit analysis" in q_lower
                    or "profit by month" in q_lower
                    or "monthly profit" in q_lower
                    or "profit trend" in q_lower
                    or "show profit" in q_lower
                ):

                    chart_result = profit_analysis_chart(
                        current_data
                    )
                # --------------------------------------------------------
                # CUSTOMER ANALYSIS — 6.7.10
                # --------------------------------------------------------

                elif (
                    "customer analysis" in q_lower
                    or "sales by customer" in q_lower
                    or "revenue by customer" in q_lower
                    or "customer comparison" in q_lower
                    or "compare customers" in q_lower
                    or "top customers" in q_lower
                    or "top customer" in q_lower
                ):

                    chart_result = customer_analysis_chart(
                        current_data
                    )            
                # --------------------------------------------------------
                # GENERAL CHART
                # --------------------------------------------------------

                else:

                    chart_result = generate_chart_data(
                        current_data
                    )

                if chart_result.get("error"):
                    return jsonify({
                        "answer": (
                            f"❌ Chart generation error: "
                            f"{chart_result['error']}"
                        )
                    })

                print(
                    "📊 Phase 6.7.2 Chart Result:",
                        chart_result
                )

                return jsonify({
                    "answer": "📊 Chart generated successfully.",
                    "chart": chart_result.get("chart", {}),
                    "data": chart_result.get("data", {}),
                    "summary": chart_result.get("summary", {}),
                    "success": True
                })

            except Exception as e:

                print(
                    "⚠️ Phase 6.7.2 Advanced Chart Engine:",
                    repr(e)
                )

                return jsonify({
                    "answer":
                        "❌ I could not generate the requested chart."
                  })
                            
        # ============================================================
        # 💡 PHASE 6.8 — BUSINESS ANALYSIS ROUTING
        # ============================================================

        if (
            "top performing areas" in q_lower
            or "worst performing areas" in q_lower
            or "business problems" in q_lower
            or "what problems do you see" in q_lower
            or "major risks" in q_lower
            or "business risks" in q_lower
            or "where should i focus" in q_lower
            or "focus my attention" in q_lower 
        ):

            try:

                analysis_result = business_analysis(
                    load_year_file("2024"),
                    load_year_file("2025")
                )

                if "top performing areas" in q_lower:

                    answer = "🏆 TOP PERFORMING AREAS\n\n"

                    for item in analysis_result["top_areas"]:

                        answer += (
                            f"• {item['area']}: "
                            f"{item['name']} "
                            f"+₹{item['change']:,.2f} "
                            f"({item['change_pct']:.2f}%)\n"
                        )

                elif "worst performing areas" in q_lower:

                    answer = "⚠️ WORST PERFORMING AREAS\n\n"

                    for item in analysis_result["worst_areas"]:

                        answer += (
                            f"• {item['area']}: "
                            f"{item['name']} "
                            f"₹{item['change']:,.2f} "
                            f"({item['change_pct']:.2f}%)\n"
                        )

                elif (
                    "business problems" in q_lower
                    or "what problems do you see" in q_lower
                ):

                    answer = "🚨 BUSINESS PROBLEMS\n\n"

                    for item in analysis_result["problems"]:

                        answer += f"• {item}\n"

                elif (
                    "major risks" in q_lower
                    or "business risks" in q_lower
                ):

                    answer = "🚨 MAJOR BUSINESS RISKS\n\n"

                    for item in analysis_result["risks"]:

                        answer += f"• {item}\n"

                else:

                    answer = "🎯 MANAGEMENT FOCUS\n\n"

                    for item in analysis_result["focus"]:

                        answer += f"• {item}\n"

                return jsonify({
                    "answer": answer,
                    "success": True
                })

            except Exception as e:

                print(
                    "⚠️ Phase 6.8:",
                    repr(e)
                )

                return jsonify({
                    "answer":
                        "❌ Business analysis could not be generated."
                })                                      
        # ============================================================
        # 🚧 PHASE 6.1 — DATASET INTELLIGENCE QUESTION ENGINE
        # ============================================================

        try:

            current_data = get_data()

            if current_data is not None and not current_data.empty:

                intelligence = profile_dataset(
                    current_data
                )

                kpis = intelligence.get(
                    "kpis",
                    {}
                )

                q_lower = question.lower().strip()

        # ----------------------------------------------------
        # TOTAL RECORDS
        # ----------------------------------------------------

                if (
                    "how many records" in q_lower
                    or "how many rows" in q_lower
                    or "number of records" in q_lower
                    or "number of rows" in q_lower
                ):

                    answer = (
                        f"The dataset contains "
                        f"{kpis.get('total_rows', len(current_data)):,} records."
                    )

                    print(
                        "Phase 6.1 Answer:",
                        repr(answer)
                    )

                    return jsonify({
                        "answer": answer
                    })

        # ----------------------------------------------------
        # TOTAL SALES
        # ----------------------------------------------------

                if (
                    "total sales" in q_lower
                    or "sales total" in q_lower
                ):

                    if "total_sales" in kpis:

                        answer = (
                            f"Total sales are "
                            f"{kpis['total_sales']:,.2f}."
                        )

                        return jsonify({
                            "answer": answer
                        })

        # ----------------------------------------------------
        # TOTAL PROFIT
        # ----------------------------------------------------

                if "total profit" in q_lower:

                    if "total_profit" in kpis:

                        answer = (
                            f"Total profit is "
                            f"{kpis['total_profit']:,.2f}."
                        )

                        return jsonify({
                            "answer": answer
                        })

        # ----------------------------------------------------
        # PROFIT MARGIN
        # ----------------------------------------------------

                if "profit margin" in q_lower:

                    if "profit_margin" in kpis:

                        answer = (
                            f"The profit margin is "
                            f"{kpis['profit_margin']:.2f}%."
                        )

                        return jsonify({
                            "answer": answer
                        })

        # ----------------------------------------------------
        # TOTAL QUANTITY
        # ----------------------------------------------------

                if (
                    "total quantity" in q_lower
                    or "quantity sold" in q_lower
                ):

                    if "total_quantity" in kpis:

                        answer = (
                            f"Total quantity is "
                            f"{kpis['total_quantity']:,.0f}."
                        )

                        return jsonify({
                            "answer": answer
                        })

        # ----------------------------------------------------
        # DATASET COLUMNS
        # ----------------------------------------------------

                if (
                    "column" in q_lower
                    or "columns" in q_lower
                ):

                    columns = intelligence[
                        "dataset"
                    ][
                        "column_names"
                    ]

                    answer = (
                        "The dataset contains these columns: "
                        + ", ".join(columns)
                        + "."
                    )

                    print(
                        "phase 6.1 answer:",
                        repr(answer)
                    )

                    return jsonify({
                        "answer": answer
                    })

        # ----------------------------------------------------
        # DATE RANGE
        # ----------------------------------------------------

                if (
                    "date range" in q_lower
                    or "date period" in q_lower
                    or "what dates" in q_lower
                    or "date covered" in q_lower
                    or "dates covered" in q_lower
                    or "start date" in q_lower
                    or "end date" in q_lower
                ):

                    if (
                        "start_date" in kpis
                        and "end_date" in kpis
                    ):  


                        answer = (
                            f"The dataset covers "
                            f"{kpis['start_date']} "
                            f"to "
                            f"{kpis['end_date']}."
                        )
                        print(
                            "phase 6.1 answer:",
                            repr(answer)
                        )

                        return jsonify({
                            "answer": answer
                        })

        except Exception as e:

            print(
                "⚠️ Phase 6.1 Question Engine:",
                repr(e)
            )            
        # ==================================================
        # 🤖 EXISTING BUSINESS INSIGHT ENGINE
        # ==================================================

        try:
            from business_insight_engine import get_business_insight

            business_answer = get_business_insight(question)

            if business_answer:
                answer = business_answer
            else:
                answer = ask_ai(question)

        except Exception as e:
            print("⚠️ Business Insight Engine:", repr(e))

            try:
                answer = ask_ai(question)

            except Exception as ask_error:

                # ask_ai() and get_business_insight() both assume
                # retail-style column names (Amount, Profit, City,
                # Product, Customer). On a dataset that doesn't have
                # those exact columns (a hospital's TreatmentCost, a
                # school's EnrollmentCount, etc.) they can raise
                # instead of answering. Rather than surface a raw
                # error, fall back to the dynamic KPI engine, which
                # was built to work with whatever columns are
                # actually detected in THIS dataset.

                print(
                    "⚠️ ask_ai also failed, falling back to "
                    "dynamic KPI engine:",
                    repr(ask_error)
                )

                try:
                    csv_data = get_data()

                    if csv_data is not None:
                        kpi_result = dynamic_kpis(csv_data)
                        answer = (
                            "I couldn't find that specific detail "
                            "in this dataset, but here's what I can "
                            "tell you from it:\n\n"
                            + format_kpi_summary(kpi_result)
                        )
                    else:
                        answer = "❌ Please upload a CSV file first."

                except Exception as fallback_error:
                    print(
                        "❌ Dynamic KPI fallback also failed:",
                        repr(fallback_error)
                    )
                    answer = (
                        "I wasn't able to answer that from this "
                        "dataset. Try asking about a specific column "
                        "or metric it contains — for example, one of "
                        "the suggested questions shown after upload."
                    )

        print("AI Answer:", repr(answer))

        # Make absolutely sure frontend receives text
        if answer is None:
            answer = "❌ No answer generated."

        elif isinstance(answer, dict):
            answer = str(answer)

        else:
            answer = str(answer)

        return jsonify({
            "answer": answer
        })

    except Exception as e:

        print("❌ ASK ERROR:", repr(e))

        return jsonify({
            "answer": (
                "❌ AI Engine Error\n\n"
                + str(e)
            )
        }), 500
@app.route("/upload", methods=["POST"])
def upload():
    """Universal upload for 1–10 business files.

    Parse each file once, keep the resulting DataFrame in memory, and only
    write a CSV snapshot for engines that still require a file path.  The old
    flow parsed a file, wrote current_data.csv, then parsed that CSV again;
    that second round-trip was the main source of fragile multi-format upload
    failures.  Every processing stage is guarded so a bad file cannot turn a
    successful upload into a generic 500 error.
    """
    files = request.files.getlist("files") or request.files.getlist("file")
    files = [f for f in files if f and f.filename]
    if not files:
        return jsonify({"success": False, "error_code": "NO_FILES", "error": "Please select at least one business file."}), 400
    if len(files) > 10:
        return jsonify({"success": False, "error_code": "TOO_MANY_FILES", "error": "You can upload a maximum of 10 files at once."}), 400

    frames, accepted, notes = [], [], []

    for upload_file in files:
        name = secure_filename(upload_file.filename)
        ext = Path(name).suffix.lower()
        if not name:
            notes.append("A selected file has an invalid filename.")
            continue
        if ext not in {".csv", ".xlsx", ".xls", ".json", ".pdf", ".docx", ".pptx"}:
            notes.append(f"{name}: unsupported file type.")
            continue

        import uuid
        stored_name = f"{uuid.uuid4().hex[:12]}_{name}"
        path = os.path.join(UPLOAD_FOLDER, stored_name)
        try:
            upload_file.save(path)
            parsed = parse_uploaded_file(path, name)
            if parsed.get("accepted") and isinstance(parsed.get("data"), pd.DataFrame):
                frames.append(parsed["data"])
                accepted.append(name)
                if parsed.get("text_fallback"):
                    notes.append(parsed["message"])
            else:
                notes.append(parsed.get("message", f"{name}: could not be read."))
        except Exception as exc:
            print(f"❌ UPLOAD PIPELINE ERROR [{name}]:", repr(exc))
            notes.append(f"{name}: {exc}")

    if not frames:
        return jsonify({
            "success": False,
            "error_code": "NO_USABLE_DATA",
            "error": "DataKite could not find usable data in the selected files.",
            "files": accepted,
            "details": notes,
        }), 422

    try:
        data = pd.concat(frames, ignore_index=True, sort=False)
        data = data.dropna(how="all").reset_index(drop=True)
        if data.empty or len(data.columns) == 0:
            raise ValueError("The combined upload contains no usable rows or columns.")

        # IMPORTANT: set the parsed DataFrame directly. Do not parse a second
        # time through CSV; this preserves Excel/Word/PPT/PDF parsing results.
        set_data(data)

        # Do not serialize the full dataset to CSV during upload. The active
        # dataset is already cached in memory; legacy path-based exports create
        # their own temporary source only when explicitly requested.

        session["analyst_history"] = []
        session.modified = True

        # Do not run heavyweight intelligence during upload. Vercel request
        # time is limited; the dashboard/AI performs analysis after the file
        # is safely loaded. This keeps upload fast and reliable.
        intelligence = {"suggested_questions": [
            "Give me a business summary",
            "Show me the key KPIs",
            "Which product performs best?",
            "Which city or region has the highest sales?",
            "Find unusual patterns in my data",
        ]}
        summary = f"Loaded {len(data):,} rows and {len(data.columns):,} columns successfully."
        dataset_id = _cache_dataset(data)
        session["dataset_id"] = dataset_id
        # Compute the initial dashboard exactly once. The browser uses this
        # payload directly, so it does not immediately POST the same dataset
        # back to /analytics/bootstrap a second time.
        dashboard = _fast_dashboard_payload(data)
        cache_item = _DATASET_CACHE.get(_dataset_cache_key(dataset_id))
        if cache_item is not None:
            cache_item["dashboard"] = dashboard
        track_event("upload", user=current_user(), success=True, file_count=len(accepted), rows=int(len(data)), columns=int(len(data.columns)), filenames=accepted[:10])

        return jsonify({
            "success": True,
            "filename": accepted[0] if len(accepted) == 1 else None,
            "filenames": accepted,
            "file_count": len(accepted),
            "type": "dataset",
            "message": summary,
            "dataset_intelligence": intelligence,
            "suggested_questions": intelligence.get("suggested_questions", []),
            "rows": int(len(data)),
            "columns": int(len(data.columns)),
            "details": notes,
            "dataset_id": dataset_id,
            "dashboard": dashboard,
        })
    except Exception as exc:
        print("❌ UPLOAD FINALIZATION ERROR:", repr(exc))
        return jsonify({
            "success": False,
            "error_code": "FINALIZATION_FAILED",
            "error": "DataKite read the files but could not finish preparing the analysis.",
            "details": [str(exc)] + notes,
        }), 500

@app.route("/chart/month-sales", methods=["GET", "POST"])
def month_sales():
    return _universal_chart("date", "sales", limit=24, monthly_mode=True)

@app.route("/chart/city-sales", methods=["GET", "POST"])
def city_sales():
    return _universal_chart("city", "sales")

@app.route("/chart/category-sales", methods=["GET", "POST"])
def category_sales():
    return _universal_chart("category", "sales")

@app.route("/chart/payment-method", methods=["GET", "POST"])
def payment_method():
    return _universal_chart("payment", "sales")

@app.route("/chart/month-profit", methods=["GET", "POST"])
def month_profit():
    return _universal_chart("date", "profit", limit=24, monthly_mode=True)

@app.route("/chart/top-products", methods=["GET", "POST"])
def top_products():
    return _universal_chart("product", "quantity", limit=5)

@app.route("/chart/top-customers", methods=["GET", "POST"])
def top_customers():
    return _universal_chart("customer", "sales", limit=5)

@app.route("/chart/order-status", methods=["GET", "POST"])
def order_status():
    data = get_data()
    if data is None or data.empty: return jsonify({"labels":[],"values":[]})
    schema = universal_schema(data); col = schema.get("status")
    if not col: return jsonify({"labels":[],"values":[],"message":"No status field detected."})
    result = data[col].astype(str).value_counts().head(10)
    return jsonify({"labels":result.index.tolist(),"values":result.values.tolist(),"field":col})

def _universal_chart(group_kind, value_kind, limit=10, monthly_mode=False):
    data = get_data()
    if data is None or data.empty: return jsonify({"labels":[],"values":[]})
    schema = universal_schema(data)
    if monthly_mode:
        result = universal_monthly(data, schema, value_kind)
        if result.empty: return jsonify({"labels":[],"values":[],"message":"No usable date/period field detected.","field":schema.get("date"),"value_field":schema.get(value_kind)})
        result = result.tail(limit)
        return jsonify({"labels":result["period"].tolist(),"values":[float(x) for x in result[value_kind].tolist()],"field":schema.get(value_kind),"date_field":schema.get("date")})
    group_col = schema.get(group_kind); value_col = schema.get(value_kind)
    result = universal_grouped(data, group_col, value_col, n=limit)
    return jsonify({"labels":result["label"].tolist(),"values":[float(x) for x in result["value"].tolist()],"field":group_col,"value_field":value_col})

@app.route("/search")
def smart_search():

    query = request.args.get("q", "").strip().lower()

    data = get_data()

    if data is None:
        return jsonify({
            "results": [],
            "message": "Please upload a file first."
        })

    if query == "":
        return jsonify({
            "results": [],
            "message": "Please enter a search term."
        })

    results = data[
        data.astype(str)
        .apply(
            lambda row: row.str.lower().str.contains(
                query,
                na=False
            ).any(),
            axis=1
        )
    ]

    return jsonify({
        "results": results.to_dict(orient="records"),
        "count": len(results)
    }) 
@app.route("/report/summary")
def report_summary():

    data = get_data()

    if data is None or data.empty:
        return jsonify({
            "error": "Please upload a file first."
        }), 400

    # ==========================================================
    # KPI SUMMARY
    # ==========================================================

    total_sales = float(data["Amount"].sum())
    total_profit = float(data["Profit"].sum())
    total_orders = int(len(data))
    customers = int(data["Customer"].nunique())
    quantity = int(data["Quantity"].sum())

    profit_margin = (
        (total_profit / total_sales) * 100
        if total_sales != 0 else 0
    )

    average_order_value = (
        total_sales / total_orders
        if total_orders != 0 else 0
    )

    kpis = {
        "total_sales": total_sales,
        "total_profit": total_profit,
        "total_orders": total_orders,
        "customers": customers,
        "quantity": quantity
    }

    # ==========================================================
    # TOP 5 PRODUCTS
    # ==========================================================

    product_summary = (
        data.groupby("Product")
        .agg(
            Sales=("Amount", "sum"),
            Profit=("Profit", "sum"),
            Quantity=("Quantity", "sum")
        )
        .sort_values("Sales", ascending=False)
        .head(5)
        .reset_index()
    )

    products = []

    for rank, (_, row) in enumerate(
        product_summary.iterrows(),
        start=1
    ):
        products.append({
            "rank": rank,
            "product": str(row["Product"]),
            "sales": float(row["Sales"]),
            "profit": float(row["Profit"]),
            "quantity": int(row["Quantity"])
        })

    # ==========================================================
    # TOP 5 CUSTOMERS
    # ==========================================================

    customer_summary = (
        data.groupby("Customer")
        .agg(
            Sales=("Amount", "sum"),
            Profit=("Profit", "sum"),
            Orders=("Amount", "count")
        )
        .sort_values("Sales", ascending=False)
        .head(5)
        .reset_index()
    )

    customers_list = []

    for rank, (_, row) in enumerate(
        customer_summary.iterrows(),
        start=1
    ):
        customers_list.append({
            "rank": rank,
            "customer": str(row["Customer"]),
            "sales": float(row["Sales"]),
            "profit": float(row["Profit"]),
            "orders": int(row["Orders"])
        })

    # ==========================================================
    # CITY ANALYSIS
    # ==========================================================

    city_list = []

    if "City" in data.columns:

        city_summary = (
            data.groupby("City")
            .agg(
                Sales=("Amount", "sum"),
                Profit=("Profit", "sum"),
                Orders=("Amount", "count")
            )
            .sort_values("Sales", ascending=False)
            .reset_index()
        )

        for _, row in city_summary.iterrows():

            city_list.append({
                "city": str(row["City"]),
                "sales": float(row["Sales"]),
                "profit": float(row["Profit"]),
                "orders": int(row["Orders"])
            })

    # ==========================================================
    # MONTHLY SALES ANALYSIS
    # ==========================================================

    monthly_list = []

    if "Date" in data.columns:

        dates = pd.to_datetime(
            data["Date"],
            errors="coerce"
        )

        monthly_data = data.copy()
        monthly_data["_date"] = dates
        monthly_data = monthly_data.dropna(
            subset=["_date"]
        )

        monthly_data["Month"] = (
            monthly_data["_date"]
            .dt.to_period("M")
            .astype(str)
        )

        monthly_summary = (
            monthly_data.groupby("Month")
            .agg(
                Sales=("Amount", "sum"),
                Profit=("Profit", "sum"),
                Orders=("Amount", "count")
            )
            .reset_index()
            .sort_values("Month")
        )

        for _, row in monthly_summary.iterrows():

            monthly_list.append({
                "month": str(row["Month"]),
                "sales": float(row["Sales"]),
                "profit": float(row["Profit"]),
                "orders": int(row["Orders"])
            })

    # ==========================================================
    # PAYMENT ANALYSIS
    # ==========================================================

    payment_list = []

    payment_column = None

    for column in [
        "Payment Method",
        "PaymentMethod",
        "Payment",
        "Payment_Type"
    ]:
        if column in data.columns:
            payment_column = column
            break

    if payment_column:

        payment_summary = (
            data.groupby(payment_column)
            .agg(
                Sales=("Amount", "sum"),
                Profit=("Profit", "sum"),
                Orders=("Amount", "count")
            )
            .sort_values("Sales", ascending=False)
            .reset_index()
        )

        for _, row in payment_summary.iterrows():

            payment_list.append({
                "payment_method": str(row[payment_column]),
                "sales": float(row["Sales"]),
                "profit": float(row["Profit"]),
                "orders": int(row["Orders"])
            })

    # ==========================================================
    # PROFITABILITY
    # ==========================================================

    profitability = {
        "total_sales": total_sales,
        "total_profit": total_profit,
        "profit_margin": profit_margin,
        "average_order_value": average_order_value
    }

    # ==========================================================
    # BUSINESS INSIGHTS
    # ==========================================================

    insights = []

    if total_sales > 0:

        insights.append(
            f"Total sales reached ₹{total_sales:,.2f}."
        )

    insights.append(
        f"Total profit generated is ₹{total_profit:,.2f}."
    )

    insights.append(
        f"The business recorded {total_orders:,} orders "
        f"from {customers:,} customers."
    )

    if profit_margin > 0:

        insights.append(
            f"Overall profit margin is {profit_margin:.2f}%."
        )

    if products:

        insights.append(
            f"{products[0]['product']} is the top-selling product "
            f"based on sales."
        )

    # ==========================================================
    # BUSINESS RECOMMENDATIONS
    # ==========================================================

    recommendations = []

    if profit_margin < 10:

        recommendations.append(
            "Focus on improving profit margins through better "
            "pricing, cost control and product mix."
        )

    else:

        recommendations.append(
            "Maintain the current profitability while identifying "
            "additional opportunities for growth."
        )

    if products:

        recommendations.append(
            f"Promote high-performing products such as "
            f"{products[0]['product']}."
        )

    if customers:

        recommendations.append(
            "Strengthen customer retention through targeted offers "
            "and repeat-purchase campaigns."
        )

    recommendations.append(
        "Monitor monthly sales and profit trends regularly "
        "to identify growth opportunities."
    )

    # ==========================================================
    # DATASET INFORMATION
    # ==========================================================

    dataset = {
        "total_records": int(len(data)),
        "total_columns": int(len(data.columns)),
        "customers": customers,
        "products": int(data["Product"].nunique()),
        "total_sales": total_sales,
        "total_profit": total_profit
    }

    # ==========================================================
    # FINAL RESPONSE
    # ==========================================================

    return jsonify({

        "kpis": kpis,

        "top_products": products,

        "top_customers": customers_list,

        "cities": city_list,

        "monthly_sales": monthly_list,

        "payments": payment_list,

        "profitability": profitability,

        "insights": insights,

        "recommendations": recommendations,

        "dataset": dataset

    })
# ==========================================================
# 📊 CREATE PROFESSIONAL CHARTS FOR PDF
# ==========================================================

def create_report_charts(data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Vercel's writable filesystem is /tmp. Reuse the production upload
    # scratch directory instead of writing beside the deployed source tree.
    chart_dir = os.path.join(UPLOAD_FOLDER, "report_charts")

    os.makedirs(chart_dir, exist_ok=True)

    chart_files = []

    data = data.copy()

    # ------------------------------------------------------
    # Numeric cleanup
    # ------------------------------------------------------

    for col in ["Amount", "Profit", "Quantity"]:
        if col in data.columns:
            data[col] = pd.to_numeric(
                data[col],
                errors="coerce"
            ).fillna(0)

    # ======================================================
    # 1. SALES BY CITY
    # ======================================================

    if "City" in data.columns:

        city = (
            data.groupby("City")["Amount"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
        )

        path = os.path.join(
            chart_dir,
            "sales_by_city.png"
        )

        plt.figure(figsize=(8, 4.5))

        city.plot(
            kind="bar",
            width=0.7
        )

        plt.title(
            "Sales by City",
            fontsize=15,
            fontweight="bold"
        )

        plt.xlabel("City")
        plt.ylabel("Sales (₹)")
        plt.xticks(rotation=35, ha="right")
        plt.grid(axis="y", alpha=0.25)
        plt.tight_layout()

        plt.savefig(
            path,
            dpi=160,
            bbox_inches="tight"
        )

        plt.close()

        chart_files.append(
            ("Sales by City", path)
        )

    # ======================================================
    # 2. SALES BY CATEGORY
    # ======================================================

    if "Category" in data.columns:

        category = (
            data.groupby("Category")["Amount"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
        )

        path = os.path.join(
            chart_dir,
            "sales_by_category.png"
        )

        plt.figure(figsize=(8, 4.5))

        category.plot(
            kind="bar",
            width=0.7
        )

        plt.title(
            "Sales by Category",
            fontsize=15,
            fontweight="bold"
        )

        plt.xlabel("Category")
        plt.ylabel("Sales (₹)")
        plt.xticks(rotation=35, ha="right")
        plt.grid(axis="y", alpha=0.25)
        plt.tight_layout()

        plt.savefig(
            path,
            dpi=160,
            bbox_inches="tight"
        )

        plt.close()

        chart_files.append(
            ("Sales by Category", path)
        )

    # ======================================================
    # 3. MONTHLY SALES
    # ======================================================

    if "Date" in data.columns:

        temp = data.copy()

        temp["Date"] = pd.to_datetime(
            temp["Date"],
            errors="coerce"
        )

        temp = temp.dropna(
            subset=["Date"]
        )

        monthly = (
            temp.groupby(
                temp["Date"].dt.to_period("M")
            )["Amount"]
            .sum()
            .sort_index()
        )

        if not monthly.empty:

            path = os.path.join(
                chart_dir,
                "monthly_sales.png"
            )

            plt.figure(figsize=(8, 4.5))

            monthly.plot(
                kind="line",
                marker="o",
                linewidth=2
            )

            plt.title(
                "Monthly Sales",
                fontsize=15,
                fontweight="bold"
            )

            plt.xlabel("Month")
            plt.ylabel("Sales (₹)")
            plt.grid(alpha=0.25)
            plt.tight_layout()

            plt.savefig(
                path,
                dpi=160,
                bbox_inches="tight"
            )

            plt.close()

            chart_files.append(
                ("Monthly Sales", path)
            )

    # ======================================================
    # 4. MONTHLY PROFIT
    # ======================================================

    if "Date" in data.columns:

        temp = data.copy()

        temp["Date"] = pd.to_datetime(
            temp["Date"],
            errors="coerce"
        )

        temp = temp.dropna(
            subset=["Date"]
        )

        monthly_profit = (
            temp.groupby(
                temp["Date"].dt.to_period("M")
            )["Profit"]
            .sum()
            .sort_index()
        )

        if not monthly_profit.empty:

            path = os.path.join(
                chart_dir,
                "monthly_profit.png"
            )

            plt.figure(figsize=(8, 4.5))

            monthly_profit.plot(
                kind="line",
                marker="o",
                linewidth=2
            )

            plt.title(
                "Monthly Profit",
                fontsize=15,
                fontweight="bold"
            )

            plt.xlabel("Month")
            plt.ylabel("Profit (₹)")
            plt.grid(alpha=0.25)
            plt.tight_layout()

            plt.savefig(
                path,
                dpi=160,
                bbox_inches="tight"
            )

            plt.close()

            chart_files.append(
                ("Monthly Profit", path)
            )

    # ======================================================
    # 5. PAYMENT METHOD
    # ======================================================

    payment_column = None

    if "Payment" in data.columns:
        payment_column = "Payment"

    elif "Payment Method" in data.columns:
        payment_column = "Payment Method"

    if payment_column:

        payment = (
            data.groupby(payment_column)["Amount"]
            .sum()
            .sort_values(ascending=False)
        )

        path = os.path.join(
            chart_dir,
            "payment_method.png"
        )

        plt.figure(figsize=(8, 4.5))

        payment.plot(
            kind="bar",
            width=0.7
        )

        plt.title(
            "Sales by Payment Method",
            fontsize=15,
            fontweight="bold"
        )

        plt.xlabel("Payment Method")
        plt.ylabel("Sales (₹)")
        plt.xticks(rotation=30, ha="right")
        plt.grid(axis="y", alpha=0.25)
        plt.tight_layout()

        plt.savefig(
            path,
            dpi=160,
            bbox_inches="tight"
        )

        plt.close()

        chart_files.append(
            ("Sales by Payment Method", path)
        )

    # ======================================================
    # 6. TOP 5 PRODUCTS
    # ======================================================

    if "Product" in data.columns:

        products = (
            data.groupby("Product")["Quantity"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        path = os.path.join(
            chart_dir,
            "top_products.png"
        )

        plt.figure(figsize=(8, 4.5))

        products.plot(
            kind="bar",
            width=0.7
        )

        plt.title(
            "Top 5 Products by Quantity",
            fontsize=15,
            fontweight="bold"
        )

        plt.xlabel("Product")
        plt.ylabel("Quantity Sold")
        plt.xticks(rotation=35, ha="right")
        plt.grid(axis="y", alpha=0.25)
        plt.tight_layout()

        plt.savefig(
            path,
            dpi=160,
            bbox_inches="tight"
        )

        plt.close()

        chart_files.append(
            ("Top 5 Products", path)
        )

    return chart_files
# ==========================================================
# 📊 EXCEL KPI SUMMARY
# ==========================================================

@app.route("/excel/kpi-summary", methods=["GET", "POST"])
def excel_kpi_summary():

    data = get_data()

    if data is None:
        return jsonify({
            "error": "Please upload a CSV or Excel file first."
        }), 400

    kpis = {
        "total_sales": float(data["Amount"].sum()),
        "total_profit": float(data["Profit"].sum()),
        "total_orders": int(len(data)),
        "total_quantity": int(data["Quantity"].sum()),
        "total_customers": int(data["Customer"].nunique())
    }

    return jsonify({
        "title": "KPI Summary",
        "kpis": kpis
    })
# ==========================================================
# 📊 PROFESSIONAL EXCEL REPORT
# ==========================================================

# ==========================================================
@app.route("/excel/download", methods=["GET", "POST"])
def excel_download():
    data = _restore_dataset_from_request()

    """Generate the premium interactive Excel dashboard with working dropdown filters."""
    if data is None or data.empty: return jsonify({"error":"Please upload a business file first."}),400
    from premium_excel_generator import build_premium_excel
    out=os.path.abspath(os.path.join(UPLOAD_FOLDER,"AI_Business_Analytics.xlsx"))
    build_premium_excel(data, out)
    return send_file(out,as_attachment=True,download_name="AI_Business_Analytics.xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/json/download", methods=["GET", "POST"])
def json_download():
    """Export the currently loaded/analyzed dataset as a portable JSON file."""
    try:
        data = _restore_dataset_from_request()
        if data is None or data.empty:
            return jsonify({"error": "Please upload a CSV or Excel file first."}), 400
        payload = {
            "source": "DataKite AI",
            "export_type": "analyzed_data_json",
            "rows": int(len(data)),
            "columns": [str(c) for c in data.columns],
            "records": json.loads(data.to_json(orient="records", date_format="iso", default_handler=str)),
        }
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        track_event("export", user=current_user(), success=True, export_type="json", rows=int(len(data)))
        return send_file(
            io.BytesIO(body),
            as_attachment=True,
            download_name="analyzed_business_data.json",
            mimetype="application/json",
        )
    except Exception as exc:
        print("❌ JSON EXPORT FAILED:", repr(exc))
        track_event("export", user=current_user(), success=False, export_type="json", error=str(exc)[:500])
        return jsonify({"error": "JSON export could not be generated.", "details": str(exc)}), 500

@app.route("/data/download", methods=["GET", "POST"])
def data_download():
    data = _restore_dataset_from_request()
    if data is None or data.empty:
        return jsonify({"error":"Please upload a business file first."}),400
    # Do not depend on /tmp/current_data.csv surviving across Vercel
    # serverless instances. Build the CSV from the dataset in this request.
    text_buf = io.StringIO()
    data.to_csv(text_buf, index=False)
    buf = io.BytesIO(text_buf.getvalue().encode("utf-8-sig"))
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name="analyzed_business_data.csv",
        mimetype="text/csv"
    )

@app.route("/downloads/<path:filename>", methods=["GET"])
def download_generated_file(filename):
    # Explicit download endpoint for export files created during the current
    # request flow. Keep filenames restricted to the upload/export directory.
    safe_name = os.path.basename(filename)
    if safe_name != filename or safe_name.startswith("."):
        return jsonify({"error": "Invalid download filename."}), 400
    path = os.path.join(UPLOAD_FOLDER, safe_name)
    if not os.path.isfile(path):
        return jsonify({"error": "The requested export is no longer available. Please export it again."}), 404
    return send_from_directory(UPLOAD_FOLDER, safe_name, as_attachment=True)

@app.route("/charts/download", methods=["GET", "POST"])
def charts_download():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data = _restore_dataset_from_request()

    if data is None or data.empty: return jsonify({"error":"Please upload a business file first."}),400
    from smart_analytics_engine import detect_schema, trend_result
    s=detect_schema(data); tr=trend_result(data,s)
    buf=io.BytesIO(); files=[]
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        if tr.get("available"):
            fig,ax=plt.subplots(figsize=(11,5)); ax.plot([r["period"] for r in tr["monthly"]],[r["sales"] for r in tr["monthly"]],marker="o"); ax.set_title("Monthly Sales Growth"); ax.tick_params(axis="x",rotation=45); fig.tight_layout(); tmp=os.path.join(UPLOAD_FOLDER,"monthly_sales.png"); fig.savefig(tmp,dpi=160); plt.close(fig); z.write(tmp,"monthly_sales.png"); os.remove(tmp)
        z.writestr("README.txt","Charts generated from the currently uploaded dataset.\n")
    buf.seek(0); return send_file(buf,as_attachment=True,download_name="AI_Business_Charts.zip",mimetype="application/zip")


def build_universal_pdf(data):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    """Generate a schema-driven PDF for any usable business dataset."""
    schema = universal_schema(data)
    sales, profit, qty = schema.get("sales"), schema.get("profit"), schema.get("quantity")
    total_sales = universal_metric(data, sales); total_profit = universal_metric(data, profit)
    orders = universal_order_count(data, schema); customers = universal_unique_count(data, schema.get("customer")); products = universal_unique_count(data, schema.get("product"))
    quantity = universal_metric(data, qty) if qty else 0
    margin = total_profit / total_sales * 100 if total_sales else 0
    aov = total_sales / orders if orders else 0
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=28, leftMargin=28, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("DKTitle", parent=styles["Title"], fontSize=22, leading=27, spaceAfter=10)
    h = ParagraphStyle("DKH", parent=styles["Heading2"], fontSize=14, leading=18, spaceBefore=12, spaceAfter=8)
    body = ParagraphStyle("DKBody", parent=styles["BodyText"], fontSize=9.5, leading=14)
    story=[Paragraph("DataKite AI — Business Analytics Report", title), Paragraph("Universal schema-driven report generated from the current dataset.", body), Spacer(1,12)]
    kpis=[["KPI","Value"],["Records",f"{len(data):,}"],["Columns",f"{len(data.columns):,}"],["Total Sales / Revenue",f"₹{total_sales:,.2f}"],["Total Profit",f"₹{total_profit:,.2f}"],["Profit Margin",f"{margin:.2f}%"],["Orders",f"{orders:,}"],["Customers",f"{customers:,}"],["Products",f"{products:,}"],["Quantity",f"{quantity:,.0f}"],["Average Order Value",f"₹{aov:,.2f}"]]
    t=Table(kpis,colWidths=[100*mm,65*mm],repeatRows=1); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#151922")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.35,colors.grey),("PADDING",(0,0),(-1,-1),7)])); story += [Paragraph("Executive Summary",h),t]
    dims=[("product","Top Products"),("category","Sales by Category"),("city","Sales by City"),("region","Sales by Region"),("payment","Sales by Payment Method")]
    for kind,title_text in dims:
        g=universal_grouped(data,schema.get(kind),sales,n=10)
        if not g.empty:
            story += [Paragraph(title_text,h)]
            rows=[["Rank","Dimension","Sales"]]+[[str(i+1),str(r.label),f"₹{float(r.value):,.2f}"] for i,r in enumerate(g.itertuples(index=False))]
            tt=Table(rows,colWidths=[18*mm,82*mm,65*mm],repeatRows=1); tt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#151922")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.35,colors.grey),("PADDING",(0,0),(-1,-1),6)])); story.append(tt)
    m=universal_monthly(data,schema,"sales")
    if not m.empty:
        story += [Paragraph("Monthly Sales Trend",h)]
        rows=[["Period","Sales"]]+[[str(r.period),f"₹{float(r.sales):,.2f}"] for r in m.tail(24).itertuples(index=False)]
        tt=Table(rows,colWidths=[70*mm,95*mm],repeatRows=1); tt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#151922")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.35,colors.grey),("PADDING",(0,0),(-1,-1),6)])); story.append(tt)
    story += [Paragraph("Detected Schema",h), Paragraph("<br/>".join(f"{k.title()}: {v or 'Not detected'}" for k,v in schema.items()), body)]
    doc.build(story)
    out.seek(0); return send_file(out,as_attachment=True,download_name="DataKite_AI_Analytics_Report.pdf",mimetype="application/pdf")

@app.route("/report/pdf", methods=["GET", "POST"])
@app.route("/pdf/download", methods=["GET", "POST"])
def pdf_download():
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    data = _restore_dataset_from_request()


    # ======================================================
    # 1. VALIDATE DATA
    # ======================================================

    if data is None or data.empty:
        return jsonify({
            "error": "Please upload a CSV or Excel file first."
        }), 400

    data = data.copy()

    # Clean column names
    data.columns = (
        data.columns
        .astype(str)
        .str.strip()
    )

    return build_universal_pdf(data)

    # Required columns
    required_columns = [
        "Amount",
        "Profit",
        "Quantity",
        "Customer",
        "Product"
    ]

    missing = [
        col
        for col in required_columns
        if col not in data.columns
    ]

    if missing:
        return jsonify({
            "error": (
                "Missing required columns: "
                + ", ".join(missing)
            )
        }), 400

    # ======================================================
    # 2. CLEAN NUMERIC DATA
    # ======================================================

    for col in [
        "Amount",
        "Profit",
        "Quantity"
    ]:
        data[col] = pd.to_numeric(
            data[col],
            errors="coerce"
        ).fillna(0)

    # ======================================================
    # 3. OUTPUT FOLDER
    # ======================================================

    upload_folder = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "uploads"
        )
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    output_path = os.path.join(
        upload_folder,
        "Business_Analytics_Report.pdf"
    )

    # ======================================================
    # 4. KPI CALCULATIONS
    # ======================================================

    total_sales = float(
        data["Amount"].sum()
    )

    total_profit = float(
        data["Profit"].sum()
    )

    total_orders = int(
        len(data)
    )

    total_quantity = int(
        data["Quantity"].sum()
    )

    total_customers = int(
        data["Customer"].nunique()
    )

    total_products = int(
        data["Product"].nunique()
    )

    profit_margin = (
        total_profit / total_sales * 100
        if total_sales
        else 0
    )

    average_order_value = (
        total_sales / total_orders
        if total_orders
        else 0
    )
    # ======================================================
    # 📊 GENERATE PDF CHARTS
    # ======================================================

    chart_files = create_report_charts(data)

    print(
        "✅ PDF charts generated:",
        chart_files
    )

    # ======================================================
    # 5. OPTIONAL FONT SUPPORT FOR ₹
    # ======================================================

    rupee_font = "Helvetica"
    rupee_bold_font = "Helvetica-Bold"

    font_candidates = [
        r"C:\Windows\Fonts\DejaVuSans.ttf",
        r"C:\Windows\Fonts\NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
    ]

    bold_font_candidates = [
        r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
        r"C:\Windows\Fonts\NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
    ]

    for font_path in font_candidates:

        if os.path.exists(font_path):

            try:
                pdfmetrics.registerFont(
                    TTFont(
                        "AppFont",
                        font_path
                    )
                )

                rupee_font = "AppFont"
                break

            except Exception:
                pass

    for font_path in bold_font_candidates:

        if os.path.exists(font_path):

            try:
                pdfmetrics.registerFont(
                    TTFont(
                        "AppFontBold",
                        font_path
                    )
                )

                rupee_bold_font = "AppFontBold"
                break

            except Exception:
                pass

    # ======================================================
    # 6. CURRENCY HELPER
    # ======================================================

    def money(value):

        return f"₹{float(value):,.2f}"

    # ======================================================
    # 7. PDF DOCUMENT
    # ======================================================

    doc = SimpleDocTemplate(

        output_path,

        pagesize=A4,

        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,

        title="Business Analytics Report",
        author="Data Analyst AI Assistant"
    )

    # ======================================================
    # 8. COLORS
    # ======================================================

    DARK_GREEN = colors.HexColor(
        "#166534"
    )

    GREEN = colors.HexColor(
        "#16A34A"
    )

    LIGHT_GREEN = colors.HexColor(
        "#F0FDF4"
    )

    VERY_LIGHT_GREEN = colors.HexColor(
        "#F7FDF8"
    )

    DARK_TEXT = colors.HexColor(
        "#1F2937"
    )

    GREY = colors.HexColor(
        "#6B7280"
    )

    BORDER = colors.HexColor(
        "#D1D5DB"
    )

    WHITE = colors.white

    # ======================================================
    # 9. STYLES
    # ======================================================

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(

        "ReportTitle",

        parent=styles["Title"],

        fontName=rupee_bold_font,

        fontSize=25,

        leading=30,

        alignment=TA_CENTER,

        textColor=DARK_GREEN,

        spaceAfter=10
    )

    subtitle_style = ParagraphStyle(

        "ReportSubtitle",

        parent=styles["BodyText"],

        fontName=rupee_font,

        fontSize=11,

        leading=15,

        alignment=TA_CENTER,

        textColor=GREY,

        spaceAfter=16
    )

    section_style = ParagraphStyle(

        "ReportSection",

        parent=styles["Heading2"],

        fontName=rupee_bold_font,

        fontSize=16,

        leading=20,

        textColor=DARK_GREEN,

        spaceBefore=6,

        spaceAfter=10
    )

    heading_style = ParagraphStyle(

        "ReportHeading",

        parent=styles["Heading3"],

        fontName=rupee_bold_font,

        fontSize=11,

        leading=14,

        textColor=DARK_GREEN,

        spaceBefore=8,

        spaceAfter=6
    )

    normal_style = ParagraphStyle(

        "ReportNormal",

        parent=styles["BodyText"],

        fontName=rupee_font,

        fontSize=9,

        leading=13,

        textColor=DARK_TEXT,

        spaceAfter=5
    )

    small_style = ParagraphStyle(

        "ReportSmall",

        parent=styles["BodyText"],

        fontName=rupee_font,

        fontSize=7.5,

        leading=10,

        textColor=GREY
    )

    # ======================================================
    # 10. TABLE HELPER
    # ======================================================

    def style_table(
        table,
        header_color=GREEN
    ):

        table.setStyle(
            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    header_color
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    WHITE
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    rupee_bold_font
                ),

                (
                    # Body rows previously had no font rule here at all, so
                    # they silently fell back to plain Helvetica (no ₹
                    # glyph) unless a later per-table setStyle() call
                    # happened to override that specific column — several
                    # tables (e.g. the Executive KPI Summary) only
                    # overrode the label column and never the value
                    # column, which is exactly where "₹361,853.04" is
                    # rendered. Confirmed visually: the ₹ showed as a
                    # black box in the KPI table's Value column even
                    # though the Unicode font was correctly registered.
                    # Setting the whole body to rupee_font here means
                    # every cell gets the Unicode-capable font by
                    # default; later per-cell overrides (e.g. bolding a
                    # label column) still apply on top of this.
                    "FONTNAME",
                    (0, 1),
                    (-1, -1),
                    rupee_font
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    BORDER
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )
            ])
        )

    # ======================================================
    # 11. PAGE FOOTER
    # ======================================================

    def add_page_footer(
        canvas,
        document
    ):

        canvas.saveState()

        canvas.setStrokeColor(
            BORDER
        )

        canvas.line(
            18 * mm,
            13 * mm,
            A4[0] - 18 * mm,
            13 * mm
        )

        canvas.setFont(
            rupee_font,
            7
        )

        canvas.setFillColor(
            GREY
        )

        canvas.drawString(
            18 * mm,
            8 * mm,
            "Data Analyst AI Assistant"
        )

        canvas.drawRightString(
            A4[0] - 18 * mm,
            8 * mm,
            f"Page {document.page}"
        )

        canvas.restoreState()

    # ======================================================
    # 12. STORY
    # ======================================================

    story = []

    # ======================================================
    # 13. COVER PAGE
    # ======================================================

    story.append(
        Spacer(
            1,
            45 * mm
        )
    )

    story.append(
        Paragraph(
            "BUSINESS ANALYTICS REPORT",
            title_style
        )
    )

    story.append(
        Paragraph(
            "Professional Sales & Customer Analytics",
            subtitle_style
        )
    )

    story.append(
        Spacer(
            1,
            15
        )
    )

    cover_data = [

        ["REPORT", "BUSINESS ANALYTICS"],

        ["RECORDS", f"{len(data):,}"],

        ["CUSTOMERS", f"{total_customers:,}"],

        ["PRODUCTS", f"{total_products:,}"],

        ["TOTAL SALES", money(total_sales)],

        ["TOTAL PROFIT", money(total_profit)],

        ["PROFIT MARGIN", f"{profit_margin:.2f}%"]
    ]

    cover_table = Table(

        cover_data,

        colWidths=[
            55 * mm,
            105 * mm
        ]
    )

    cover_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                LIGHT_GREEN
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (0, -1),
                DARK_GREEN
            ),

            (
                "FONTNAME",
                (0, 0),
                (0, -1),
                rupee_bold_font
            ),

            (
                "FONTNAME",
                (1, 0),
                (1, -1),
                rupee_font
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                BORDER
            ),

            (
                "PADDING",
                (0, 0),
                (-1, -1),
                9
            )
        ])
    )

    story.append(
        cover_table
    )

    story.append(
        Spacer(
            1,
            25
        )
    )

    story.append(
        Paragraph(
            "Generated by Data Analyst AI Assistant",
            subtitle_style
        )
    )

    story.append(
        PageBreak()
    )

    # ======================================================
    # 14. EXECUTIVE KPI SUMMARY
    # ======================================================

    story.append(
        Paragraph(
            "1. Executive KPI Summary",
            section_style
        )
    )

    kpi_data = [

        ["KPI", "Value"],

        ["Total Sales", money(total_sales)],

        ["Total Profit", money(total_profit)],

        ["Total Orders", f"{total_orders:,}"],

        ["Total Quantity", f"{total_quantity:,}"],

        ["Total Customers", f"{total_customers:,}"],

        ["Total Products", f"{total_products:,}"],

        ["Profit Margin", f"{profit_margin:.2f}%"],

        ["Average Order Value", money(average_order_value)]
    ]

    kpi_table = Table(

        kpi_data,

        colWidths=[
            85 * mm,
            75 * mm
        ],

        repeatRows=1
    )

    style_table(
        kpi_table,
        DARK_GREEN
    )

    kpi_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                VERY_LIGHT_GREEN
            ),

            (
                "FONTNAME",
                (0, 1),
                (0, -1),
                rupee_bold_font
            ),

            (
                "ALIGN",
                (1, 1),
                (1, -1),
                "RIGHT"
            )
        ])
    )

    story.append(
        kpi_table
    )

    story.append(
        Spacer(
            1,
            15
        )
    )

    story.append(
        Paragraph(
            "This section provides a high-level overview of the "
            "uploaded business dataset, including sales, profit, "
            "orders, customers, quantity and profitability.",
            normal_style
        )
    )

    story.append(
        PageBreak()
    )

    # ======================================================
    # 15. TOP PRODUCTS
    # ======================================================

    story.append(
        Paragraph(
            "2. Top 10 Products",
            section_style
        )
    )

    top_products = (
        data.groupby("Product")
        .agg(
            Sales=("Amount", "sum"),
            Profit=("Profit", "sum"),
            Quantity=("Quantity", "sum")
        )
        .sort_values(
            "Sales",
            ascending=False
        )
        .head(10)
        .reset_index()
    )

    product_data = [

        [
            "Rank",
            "Product",
            "Sales",
            "Profit",
            "Quantity"
        ]
    ]

    for rank, (_, row) in enumerate(
        top_products.iterrows(),
        start=1
    ):

        product_data.append([

            str(rank),

            str(row["Product"]),

            money(row["Sales"]),

            money(row["Profit"]),

            f"{int(row['Quantity']):,}"
        ])

    product_table = Table(

        product_data,

        colWidths=[
            15 * mm,
            55 * mm,
            35 * mm,
            35 * mm,
            25 * mm
        ],

        repeatRows=1
    )

    style_table(
        product_table,
        GREEN
    )

    product_table.setStyle(
        TableStyle([

            (
                "ALIGN",
                (0, 1),
                (0, -1),
                "CENTER"
            ),

            (
                "ALIGN",
                (2, 1),
                (-1, -1),
                "RIGHT"
            )
        ])
    )

    story.append(
        product_table
    )

    story.append(
        Spacer(
            1,
            15
        )
    )

    if not top_products.empty:

        best_product = str(
            top_products.iloc[0]["Product"]
        )

        best_product_sales = float(
            top_products.iloc[0]["Sales"]
        )

        story.append(
            Paragraph(
                f"<b>Key finding:</b> {best_product} "
                f"is the highest-sales product with "
                f"{money(best_product_sales)} in sales.",
                normal_style
            )
        )

    story.append(
        PageBreak()
    )

    # ======================================================
    # 16. TOP CUSTOMERS
    # ======================================================

    story.append(
        Paragraph(
            "3. Top 10 Customers",
            section_style
        )
    )

    top_customers = (
        data.groupby("Customer")
        .agg(
            Sales=("Amount", "sum"),
            Profit=("Profit", "sum"),
            Orders=("Amount", "count")
        )
        .sort_values(
            "Sales",
            ascending=False
        )
        .head(10)
        .reset_index()
    )

    customer_data = [

        [
            "Rank",
            "Customer",
            "Sales",
            "Profit",
            "Orders"
        ]
    ]

    for rank, (_, row) in enumerate(
        top_customers.iterrows(),
        start=1
    ):

        customer_data.append([

            str(rank),

            str(row["Customer"]),

            money(row["Sales"]),

            money(row["Profit"]),

            f"{int(row['Orders']):,}"
        ])

    customer_table = Table(

        customer_data,

        colWidths=[
            15 * mm,
            55 * mm,
            35 * mm,
            35 * mm,
            25 * mm
        ],

        repeatRows=1
    )

    style_table(
        customer_table,
        GREEN
    )

    customer_table.setStyle(
        TableStyle([

            (
                "ALIGN",
                (0, 1),
                (0, -1),
                "CENTER"
            ),

            (
                "ALIGN",
                (2, 1),
                (-1, -1),
                "RIGHT"
            )
        ])
    )

    story.append(
        customer_table
    )

    story.append(
        PageBreak()
    )

    # ======================================================
    # 17. CITY ANALYSIS
    # ======================================================

    story.append(
        Paragraph(
            "4. City Analysis",
            section_style
        )
    )

    if "City" in data.columns:

        city = (
            data.groupby("City")
            .agg(
                Sales=("Amount", "sum"),
                Profit=("Profit", "sum"),
                Orders=("Amount", "count")
            )
            .sort_values(
                "Sales",
                ascending=False
            )
            .reset_index()
        )

        city_data = [
            [
                "City",
                "Sales",
                "Profit",
                "Orders"
            ]
        ]

        for _, row in city.iterrows():

            city_data.append([

                str(row["City"]),

                money(row["Sales"]),

                money(row["Profit"]),

                f"{int(row['Orders']):,}"
            ])

        city_table = Table(
            city_data,
            colWidths=[
                65 * mm,
                40 * mm,
                40 * mm,
                25 * mm
            ],
            repeatRows=1
        )

        style_table(
            city_table,
            DARK_GREEN
        )

        city_table.setStyle(
            TableStyle([
                (
                    "ALIGN",
                    (1, 1),
                    (-1, -1),
                    "RIGHT"
                )
            ])
        )

        story.append(
            city_table
        )

    else:

        story.append(
            Paragraph(
                "City column is not available.",
                normal_style
            )
        )

    story.append(
        PageBreak()
    )

    # ======================================================
    # 18. MONTHLY SALES
    # ======================================================

    story.append(
        Paragraph(
            "5. Monthly Sales Analysis",
            section_style
        )
    )

    monthly_available = False

    if "Date" in data.columns:

        temp = data.copy()

        temp["Date"] = pd.to_datetime(
            temp["Date"],
            errors="coerce"
        )

        temp = temp.dropna(
            subset=["Date"]
        )

        if not temp.empty:

            monthly_available = True

            monthly = (
                temp.groupby(
                    temp["Date"].dt.to_period("M")
                )
                .agg(
                    Sales=("Amount", "sum"),
                    Profit=("Profit", "sum"),
                    Orders=("Amount", "count")
                )
                .reset_index()
            )

            monthly["Date"] = (
                monthly["Date"].astype(str)
            )

            monthly_data = [
                [
                    "Month",
                    "Sales",
                    "Profit",
                    "Orders"
                ]
            ]

            for _, row in monthly.iterrows():

                monthly_data.append([

                    str(row["Date"]),

                    money(row["Sales"]),

                    money(row["Profit"]),

                    f"{int(row['Orders']):,}"
                ])

            monthly_table = Table(
                monthly_data,
                colWidths=[
                    55 * mm,
                    45 * mm,
                    45 * mm,
                    25 * mm
                ],
                repeatRows=1
            )

            style_table(
                monthly_table,
                GREEN
            )

            monthly_table.setStyle(
                TableStyle([
                    (
                        "ALIGN",
                        (1, 1),
                        (-1, -1),
                        "RIGHT"
                    )
                ])
            )

            story.append(
                monthly_table
            )

    if not monthly_available:

        story.append(
            Paragraph(
                "Date column is not available, "
                "so monthly analysis could not be generated.",
                normal_style
            )
        )

    story.append(
        PageBreak()
    )

    # ======================================================
    # 19. PAYMENT ANALYSIS
    # ======================================================

    story.append(
        Paragraph(
            "6. Payment Analysis",
            section_style
        )
    )

    payment_column = None

    if "Payment" in data.columns:
        payment_column = "Payment"

    elif "Payment Method" in data.columns:
        payment_column = "Payment Method"

    if payment_column:

        payment = (
            data.groupby(payment_column)
            .agg(
                Sales=("Amount", "sum"),
                Profit=("Profit", "sum"),
                Orders=("Amount", "count")
            )
            .sort_values(
                "Sales",
                ascending=False
            )
            .reset_index()
        )

        payment_data = [
            [
                "Payment Method",
                "Sales",
                "Profit",
                "Orders"
            ]
        ]

        for _, row in payment.iterrows():

            payment_data.append([

                str(row[payment_column]),

                money(row["Sales"]),

                money(row["Profit"]),

                f"{int(row['Orders']):,}"
            ])

        payment_table = Table(
            payment_data,
            colWidths=[
                60 * mm,
                40 * mm,
                40 * mm,
                25 * mm
            ],
            repeatRows=1
        )

        style_table(
            payment_table,
            DARK_GREEN
        )

        payment_table.setStyle(
            TableStyle([
                (
                    "ALIGN",
                    (1, 1),
                    (-1, -1),
                    "RIGHT"
                )
            ])
        )

        story.append(
            payment_table
        )

    else:

        story.append(
            Paragraph(
                "Payment method column is not available.",
                normal_style
            )
        )

    story.append(
        PageBreak()
    )

    # ======================================================
    # 20. PROFITABILITY ANALYSIS
    # ======================================================

    story.append(
        Paragraph(
            "7. Profitability Analysis",
            section_style
        )
    )

    profit_data = [

        ["Metric", "Value"],

        ["Total Sales", money(total_sales)],

        ["Total Profit", money(total_profit)],

        ["Profit Margin", f"{profit_margin:.2f}%"],

        ["Average Order Value", money(average_order_value)]
    ]

    profit_table = Table(

        profit_data,

        colWidths=[
            85 * mm,
            75 * mm
        ],

        repeatRows=1
    )

    style_table(
        profit_table,
        GREEN
    )

    profit_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                LIGHT_GREEN
            ),

            (
                "FONTNAME",
                (0, 1),
                (0, -1),
                rupee_bold_font
            ),

            (
                "ALIGN",
                (1, 1),
                (1, -1),
                "RIGHT"
            )
        ])
    )

    story.append(
        profit_table
    )

    story.append(
        Spacer(
            1,
            15
        )
    )

    if total_profit > 0:

        profit_message = (
            "The dataset shows positive overall profitability."
        )

    elif total_profit < 0:

        profit_message = (
            "The dataset shows an overall negative profit."
        )

    else:

        profit_message = (
            "The dataset shows zero overall profit."
        )

    story.append(
        Paragraph(
            profit_message,
            normal_style
        )
    )

    story.append(
        PageBreak()
    )

    # ======================================================
    # 21. BUSINESS INSIGHTS
    # ======================================================

    story.append(
        Paragraph(
            "8. Business Insights",
            section_style
        )
    )

    insights = []

    if not top_products.empty:

        insights.append(
            f"{top_products.iloc[0]['Product']} "
            "is the highest-sales product."
        )

    if not top_customers.empty:

        insights.append(
            f"{top_customers.iloc[0]['Customer']} "
            "is the highest-value customer."
        )

    if "City" in data.columns:

        city_sales = (
            data.groupby("City")["Amount"]
            .sum()
            .sort_values(
                ascending=False
            )
        )

        if not city_sales.empty:

            insights.append(
                f"{city_sales.index[0]} "
                "is the strongest city by sales."
            )

    if "Category" in data.columns:

        category_sales = (
            data.groupby("Category")["Amount"]
            .sum()
            .sort_values(
                ascending=False
            )
        )

        if not category_sales.empty:

            insights.append(
                f"{category_sales.index[0]} "
                "is the leading category by sales."
            )

    insights.append(
        f"The business generated {money(total_profit)} "
        "in total profit."
    )

    insights.append(
        f"The overall profit margin is "
        f"{profit_margin:.2f}%."
    )

    insights.append(
        f"The dataset contains {total_orders:,} orders "
        f"from {total_customers:,} customers."
    )

    for insight in insights:

        story.append(
            Paragraph(
                "• " + insight,
                normal_style
            )
        )

    # ======================================================
    # 22. RECOMMENDATIONS
    # ======================================================

    story.append(
        Spacer(
            1,
            10
        )
    )

    story.append(
        Paragraph(
            "9. Business Recommendations",
            section_style
        )
    )

    recommendations = [

        "Maintain sufficient inventory for high-performing products.",

        "Develop retention strategies for high-value customers.",

        "Monitor city-level performance and identify weaker markets.",

        "Track monthly sales and profit trends consistently.",

        "Review products with high sales but comparatively low profit.",

        "Evaluate payment-method performance to improve customer convenience.",

        "Use sales and profitability trends to guide future marketing and inventory decisions."
    ]

    for recommendation in recommendations:

        story.append(
            Paragraph(
                "• " + recommendation,
                normal_style
            )
        )

    story.append(
        PageBreak()
    )

    # ======================================================
    # 23. DATASET INFORMATION
    # ======================================================

    story.append(
        Paragraph(
            "10. Dataset Information",
            section_style
        )
    )

    dataset_info = [

        ["Information", "Value"],

        ["Total Records", f"{len(data):,}"],

        ["Total Columns", f"{len(data.columns):,}"],

        ["Customers", f"{total_customers:,}"],

        ["Products", f"{total_products:,}"],

        ["Total Sales", money(total_sales)],

        ["Total Profit", money(total_profit)]
    ]

    dataset_table = Table(

        dataset_info,

        colWidths=[
            85 * mm,
            75 * mm
        ],

        repeatRows=1
    )

    style_table(
        dataset_table,
        DARK_GREEN
    )

    dataset_table.setStyle(
        TableStyle([

            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                VERY_LIGHT_GREEN
            ),

            (
                "ALIGN",
                (1, 1),
                (1, -1),
                "RIGHT"
            )
        ])
    )

    story.append(
        dataset_table
    )

    story.append(
        Spacer(
            1,
            15
        )
    )

    story.append(
        Paragraph(
            "<b>Available columns:</b> "
            + ", ".join(
                map(str, data.columns)
            ),
            small_style
        )
    )
    # ======================================================
    # 📊 INSERT ALL CHARTS INTO PDF
    # ======================================================

    if chart_files:

        story.append(
            PageBreak()
        )

        story.append(
            Paragraph(
                "Business Analytics Charts",
                section_style
            )
        )

        for title, chart_path in chart_files:

            story.append(
                Paragraph(
                    title,
                    section_style
                )
            )

            try:

                story.append(
                    Image(
                        chart_path,
                        width=170 * mm,
                        height=90 * mm
                    )
                )

            except Exception as chart_error:

                story.append(
                    Paragraph(
                        f"Chart could not be inserted: {chart_error}",
                        normal_style
                    )
                )

            story.append(
                Spacer(1, 12)
        )

    # ======================================================
    # 24. FINAL BUILD
    # ======================================================

    doc.build(

        story,

        onFirstPage=add_page_footer,

        onLaterPages=add_page_footer
    )

    print(
        "✅ Professional PDF generated:",
        output_path
    )

    return send_file(

        output_path,

        as_attachment=True,

        download_name="Business_Analytics_Report.pdf",

        mimetype="application/pdf"
    )
# ==========================================================
# 📝 PROFESSIONAL WORD REPORT
# ==========================================================

def _export_metrics(data, schema=None):
    """Small, shared metric calculation for document exports."""
    schema = schema or universal_schema(data)
    sales_col = schema.get("sales")
    profit_col = schema.get("profit")
    qty_col = schema.get("quantity")
    total_sales = universal_metric(data, sales_col) if sales_col else 0
    total_profit = universal_metric(data, profit_col) if profit_col else 0
    total_quantity = universal_metric(data, qty_col) if qty_col else 0
    total_orders = universal_order_count(data, schema)
    total_customers = universal_unique_count(data, schema.get("customer"))
    total_products = universal_unique_count(data, schema.get("product"))
    profit_margin = (total_profit / total_sales * 100) if total_sales else 0
    average_order_value = (total_sales / total_orders) if total_orders else 0
    return {
        "total_sales": float(total_sales or 0),
        "total_profit": float(total_profit or 0),
        "total_quantity": float(total_quantity or 0),
        "total_orders": int(total_orders or 0),
        "total_customers": int(total_customers or 0),
        "total_products": int(total_products or 0),
        "profit_margin": float(profit_margin or 0),
        "average_order_value": float(average_order_value or 0),
    }


def _word_download_impl():
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor as DocxRGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.section import WD_SECTION
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    data = _restore_dataset_from_request()


    if data is None or data.empty:
        return jsonify({
            "error": "Please upload a CSV or Excel file first."
        }), 400

    data = data.copy()
    data.columns = data.columns.astype(str).str.strip()
    schema = universal_schema(data)
    metrics = _export_metrics(data, schema)
    total_sales = metrics["total_sales"]
    total_profit = metrics["total_profit"]
    total_quantity = metrics["total_quantity"]
    total_orders = metrics["total_orders"]
    total_customers = metrics["total_customers"]
    total_products = metrics["total_products"]
    profit_margin = metrics["profit_margin"]
    average_order_value = metrics["average_order_value"]

    # Universal export aliases: map common business concepts to the
    # generator's internal names so real-world headers are accepted.
    export_map = {
        "Amount": schema.get("sales"),
        "Profit": schema.get("profit"),
        "Quantity": schema.get("quantity"),
        "Customer": schema.get("customer"),
        "Product": schema.get("product"),
        "City": schema.get("city"),
        "Category": schema.get("category"),
        "Date": schema.get("date"),
        "Payment": schema.get("payment"),
        "Status": schema.get("status"),
    }
    for canonical, source in export_map.items():
        if source and source in data.columns and canonical not in data.columns:
            data[canonical] = data[source]

    if "Amount" not in data.columns:
        return jsonify({"error": "No usable sales/revenue/amount field was detected in this dataset."}), 400
    for col in ["Profit", "Quantity"]:
        if col not in data.columns:
            data[col] = 0
    for col in ["Customer", "Product"]:
        if col not in data.columns:
            data[col] = pd.Series([None] * len(data), index=data.index)

    for col in ["Amount", "Profit", "Quantity"]:
        data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0)

    def money(value):
        return f"₹{float(value):,.2f}"

    # ------------------------------------------------------
    # Document setup
    # ------------------------------------------------------

    doc = Document()

    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)

    # ------------------------------------------------------
    # Styles
    # ------------------------------------------------------

    styles = doc.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(10)

    GREEN = DocxRGBColor(22, 163, 74)
    DARK_GREEN = DocxRGBColor(22, 101, 52)
    DARK_TEXT = DocxRGBColor(31, 41, 55)
    WHITE = DocxRGBColor(255, 255, 255)

    def set_cell_shading(cell, fill):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = tcPr.find(qn("w:shd"))
        if shd is None:
            shd = OxmlElement("w:shd")
            tcPr.append(shd)
        shd.set(qn("w:fill"), fill)

    def set_cell_text(cell, text, bold=False, color=None, size=9):
        cell.text = ""
        paragraph = cell.paragraphs[0]
        run = paragraph.add_run(str(text))
        run.bold = bold
        run.font.size = Pt(size)
        if color:
            run.font.color.rgb = color
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def add_heading(text, level=1):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(text)
        run.bold = True
        run.font.color.rgb = DARK_GREEN
        run.font.size = Pt(16 if level == 1 else 12)
        return p

    def add_table(headers, rows, widths=None):
        table = doc.add_table(
            rows=1,
            cols=len(headers)
        )
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"

        for i, header in enumerate(headers):
            cell = table.rows[0].cells[i]
            set_cell_text(cell, header, True, WHITE, 9)
            set_cell_shading(cell, "16A34A")

        for row in rows:
            cells = table.add_row().cells
            for i, value in enumerate(row):
                set_cell_text(cells[i], value, False, DARK_TEXT, 8.5)

        if widths:
            for row in table.rows:
                for i, width in enumerate(widths):
                    row.cells[i].width = Inches(width)

        doc.add_paragraph()
        return table

    def add_bullet(text):
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(4)
        p.add_run(str(text))
        return p

    def add_footer(section_obj):
        footer = section_obj.footer
        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("Data Analyst AI Assistant")
        run.font.size = Pt(8)
        run.font.color.rgb = DocxRGBColor(107, 114, 128)

    add_footer(section)

    # ------------------------------------------------------
    # Cover page
    # ------------------------------------------------------

    for _ in range(4):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("BUSINESS ANALYTICS REPORT")
    run.bold = True
    run.font.size = Pt(27)
    run.font.color.rgb = DARK_GREEN

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Professional Sales & Customer Analytics")
    run.font.size = Pt(12)
    run.font.color.rgb = DocxRGBColor(107, 114, 128)

    doc.add_paragraph()

    cover_rows = [
        ["Records", f"{len(data):,}"],
        ["Customers", f"{total_customers:,}"],
        ["Products", f"{total_products:,}"],
        ["Total Sales", money(total_sales)],
        ["Total Profit", money(total_profit)],
        ["Profit Margin", f"{profit_margin:.2f}%"]
    ]

    add_table(
        ["Report Metric", "Value"],
        cover_rows,
        [2.4, 2.8]
    )

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Generated by Data Analyst AI Assistant")
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = DocxRGBColor(107, 114, 128)

    doc.add_page_break()

    # ------------------------------------------------------
    # Executive summary
    # ------------------------------------------------------

    add_heading("1. Executive Summary")

    p = doc.add_paragraph()
    p.add_run(
        "The uploaded dataset contains "
        f"{total_orders:,} orders from {total_customers:,} customers "
        f"across {total_products:,} products. Total sales are "
        f"{money(total_sales)}, while total profit is "
        f"{money(total_profit)}, producing an overall profit margin "
        f"of {profit_margin:.2f}%."
    )

    add_table(
        ["KPI", "Value"],
        [
            ["Total Sales", money(total_sales)],
            ["Total Profit", money(total_profit)],
            ["Total Orders", f"{total_orders:,}"],
            ["Total Quantity", f"{total_quantity:,}"],
            ["Total Customers", f"{total_customers:,}"],
            ["Total Products", f"{total_products:,}"],
            ["Profit Margin", f"{profit_margin:.2f}%"],
            ["Average Order Value", money(average_order_value)]
        ],
        [2.8, 2.4]
    )

    doc.add_page_break()

    # ------------------------------------------------------
    # Top products
    # ------------------------------------------------------

    add_heading("2. Top 10 Products")

    top_products_df = (
        data.groupby("Product")
        .agg(
            Sales=("Amount", "sum"),
            Profit=("Profit", "sum"),
            Quantity=("Quantity", "sum")
        )
        .sort_values("Sales", ascending=False)
        .head(10)
        .reset_index()
    )

    product_rows = []
    for rank, (_, row) in enumerate(
        top_products_df.iterrows(),
        start=1
    ):
        product_rows.append([
            rank,
            row["Product"],
            money(row["Sales"]),
            money(row["Profit"]),
            f"{int(row['Quantity']):,}"
        ])

    add_table(
        ["Rank", "Product", "Sales", "Profit", "Quantity"],
        product_rows,
        [0.5, 2.0, 1.3, 1.3, 1.0]
    )

    if not top_products_df.empty:
        add_bullet(
            f"{top_products_df.iloc[0]['Product']} is the highest-sales product."
        )

    doc.add_page_break()

    # ------------------------------------------------------
    # Top customers
    # ------------------------------------------------------

    add_heading("3. Top 10 Customers")

    top_customers_df = (
        data.groupby("Customer")
        .agg(
            Sales=("Amount", "sum"),
            Profit=("Profit", "sum"),
            Orders=("Amount", "count")
        )
        .sort_values("Sales", ascending=False)
        .head(10)
        .reset_index()
    )

    customer_rows = []
    for rank, (_, row) in enumerate(
        top_customers_df.iterrows(),
        start=1
    ):
        customer_rows.append([
            rank,
            row["Customer"],
            money(row["Sales"]),
            money(row["Profit"]),
            f"{int(row['Orders']):,}"
        ])

    add_table(
        ["Rank", "Customer", "Sales", "Profit", "Orders"],
        customer_rows,
        [0.5, 2.0, 1.3, 1.3, 1.0]
    )

    doc.add_page_break()

    # ------------------------------------------------------
    # City analysis
    # ------------------------------------------------------

    add_heading("4. City Analysis")

    if "City" in data.columns:
        city_df = (
            data.groupby("City")
            .agg(
                Sales=("Amount", "sum"),
                Profit=("Profit", "sum"),
                Orders=("Amount", "count")
            )
            .sort_values("Sales", ascending=False)
            .reset_index()
        )

        city_rows = [
            [
                row["City"],
                money(row["Sales"]),
                money(row["Profit"]),
                f"{int(row['Orders']):,}"
            ]
            for _, row in city_df.iterrows()
        ]

        add_table(
            ["City", "Sales", "Profit", "Orders"],
            city_rows,
            [2.1, 1.5, 1.5, 1.0]
        )
    else:
        doc.add_paragraph("City column is not available.")

    doc.add_page_break()

    # ------------------------------------------------------
    # Monthly sales
    # ------------------------------------------------------

    add_heading("5. Monthly Sales Analysis")

    monthly_df = None

    if "Date" in data.columns:

        temp = data.copy()

        temp["Date"] = pd.to_datetime(
            temp["Date"],
            errors="coerce"
        )

        temp = temp.dropna(subset=["Date"])

        if not temp.empty:

            monthly_df = (
                temp.groupby(temp["Date"].dt.to_period("M"))
                .agg(
                    Sales=("Amount", "sum"),
                    Profit=("Profit", "sum"),
                    Orders=("Amount", "count")
                )
                .reset_index()
            )
            monthly_df["Date"] = monthly_df["Date"].astype(str)

    if monthly_df is not None and not monthly_df.empty:
        monthly_rows = [
            [
                row["Date"],
                money(row["Sales"]),
                money(row["Profit"]),
                f"{int(row['Orders']):,}"
            ]
            for _, row in monthly_df.iterrows()
        ]

        add_table(
            ["Month", "Sales", "Profit", "Orders"],
            monthly_rows,
            [1.3, 1.8, 1.8, 1.1]
        )
    else:
        doc.add_paragraph(
            "Date column is not available, so monthly analysis could not be generated."
        )

    doc.add_page_break()

    # ------------------------------------------------------
    # Payment analysis
    # ------------------------------------------------------

    add_heading("6. Payment Analysis")

    payment_column = None
    if "Payment" in data.columns:
        payment_column = "Payment"
    elif "Payment Method" in data.columns:
        payment_column = "Payment Method"

    if payment_column:
        payment_df = (
            data.groupby(payment_column)
            .agg(
                Sales=("Amount", "sum"),
                Profit=("Profit", "sum"),
                Orders=("Amount", "count")
            )
            .sort_values("Sales", ascending=False)
            .reset_index()
        )

        payment_rows = [
            [
                row[payment_column],
                money(row["Sales"]),
                money(row["Profit"]),
                f"{int(row['Orders']):,}"
            ]
            for _, row in payment_df.iterrows()
        ]

        add_table(
            ["Payment Method", "Sales", "Profit", "Orders"],
            payment_rows,
            [2.0, 1.6, 1.6, 1.0]
        )
    else:
        doc.add_paragraph("Payment method column is not available.")

    doc.add_page_break()

    # ------------------------------------------------------
    # Profitability
    # ------------------------------------------------------

    add_heading("7. Profitability Analysis")

    add_table(
        ["Metric", "Value"],
        [
            ["Total Sales", money(total_sales)],
            ["Total Profit", money(total_profit)],
            ["Profit Margin", f"{profit_margin:.2f}%"],
            ["Average Order Value", money(average_order_value)]
        ],
        [2.8, 2.4]
    )

    if total_profit > 0:
        add_bullet("The dataset shows positive overall profitability.")
    elif total_profit < 0:
        add_bullet("The dataset shows an overall negative profit.")
    else:
        add_bullet("The dataset shows zero overall profit.")

    doc.add_page_break()

    # ------------------------------------------------------
    # Charts
    # ------------------------------------------------------

    add_heading("8. Business Analytics Charts")
    doc.add_paragraph(
        "Visual analysis of sales, profit, products and payment performance."
    )

    try:
        chart_files = create_report_charts(data)
    except Exception as chart_generation_error:
        print("⚠️ WORD REPORT CHARTS SKIPPED:", repr(chart_generation_error))
        chart_files = []
        doc.add_paragraph(
            "Charts could not be generated in this export environment; the written analysis and KPI tables are still included."
        )

    for chart_title, chart_path in chart_files:
        if not os.path.exists(chart_path):
            continue

        p = doc.add_paragraph()
        r = p.add_run(chart_title)
        r.bold = True
        r.font.size = Pt(12)
        r.font.color.rgb = DARK_GREEN

        try:
            doc.add_picture(
                chart_path,
                width=Inches(6.2)
            )
            last = doc.paragraphs[-1]
            last.alignment = WD_ALIGN_PARAGRAPH.CENTER
        except Exception as chart_error:
            doc.add_paragraph(
                f"Chart could not be inserted: {chart_error}"
            )

        doc.add_paragraph()

    doc.add_page_break()

    # ------------------------------------------------------
    # Business insights
    # ------------------------------------------------------

    add_heading("9. Business Insights")

    insights = []

    if not top_products_df.empty:
        insights.append(
            f"{top_products_df.iloc[0]['Product']} is the highest-sales product."
        )

    if not top_customers_df.empty:
        insights.append(
            f"{top_customers_df.iloc[0]['Customer']} is the highest-value customer."
        )

    if "City" in data.columns:
        city_sales = (
            data.groupby("City")["Amount"]
            .sum()
            .sort_values(ascending=False)
        )
        if not city_sales.empty:
            insights.append(
                f"{city_sales.index[0]} is the strongest city by sales."
            )

    if "Category" in data.columns:
        category_sales = (
            data.groupby("Category")["Amount"]
            .sum()
            .sort_values(ascending=False)
        )
        if not category_sales.empty:
            insights.append(
                f"{category_sales.index[0]} is the leading category by sales."
            )

    insights.extend([
        f"The business generated {money(total_profit)} in total profit.",
        f"The overall profit margin is {profit_margin:.2f}%.",
        f"The dataset contains {total_orders:,} orders from {total_customers:,} customers."
    ])

    for insight in insights:
        add_bullet(insight)

    doc.add_page_break()

    # ------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------

    add_heading("10. Business Recommendations")

    recommendations = [
        "Maintain sufficient inventory for high-performing products.",
        "Develop retention strategies for high-value customers.",
        "Monitor city-level performance and identify weaker markets.",
        "Track monthly sales and profit trends consistently.",
        "Review products with high sales but comparatively low profit.",
        "Evaluate payment-method performance to improve customer convenience.",
        "Use sales and profitability trends to guide future marketing and inventory decisions."
    ]

    for recommendation in recommendations:
        add_bullet(recommendation)

    doc.add_page_break()

    # ------------------------------------------------------
    # Dataset information
    # ------------------------------------------------------

    add_heading("11. Dataset Information")

    add_table(
        ["Information", "Value"],
        [
            ["Total Records", f"{len(data):,}"],
            ["Total Columns", f"{len(data.columns):,}"],
            ["Customers", f"{total_customers:,}"],
            ["Products", f"{total_products:,}"],
            ["Total Sales", money(total_sales)],
            ["Total Profit", money(total_profit)]
        ],
        [2.8, 2.4]
    )

    p = doc.add_paragraph()
    r = p.add_run(
        "Available columns: " + ", ".join(map(str, data.columns))
    )
    r.font.size = Pt(8)
    r.font.color.rgb = DocxRGBColor(107, 114, 128)

    # ------------------------------------------------------
    # Save
    # ------------------------------------------------------

    output_path = os.path.join(
        UPLOAD_FOLDER,
        "Business_Analytics_Report.docx"
    )
    doc.save(output_path)

    print(
        "✅ Professional Word report generated:",
        output_path
    )

    return send_file(
        output_path,
        as_attachment=True,
        download_name="Business_Analytics_Report.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

@app.route("/word/download", methods=["GET", "POST"])
def word_download():
    """Generate the professional Word report, with a dependency-safe fallback."""
    try:
        return _word_download_impl()
    except Exception as exc:
        print("⚠️ WORD EXPORT FALLBACK:", repr(exc))
        data = _restore_dataset_from_request()
        if data is None or data.empty:
            return jsonify({"error": "Please upload a business file first."}), 400
        try:
            schema = universal_schema(data)
            metrics = _export_metrics(data, schema)
            from xml.sax.saxutils import escape as _xml_escape
            import zipfile as _zf
            import io as _io
            out = _io.BytesIO()
            def para(text, bold=False, size=22):
                text = _xml_escape(str(text))
                rpr = f'<w:rPr><w:b/><w:sz w:val="{size}"/></w:rPr>' if bold else f'<w:rPr><w:sz w:val="{size}"/></w:rPr>'
                return f'<w:p><w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
            body = "".join([
                para("DataKite AI — Business Analytics Report", True, 32),
                para(f"Records: {len(data):,}"),
                para(f"Columns: {len(data.columns):,}"),
                para(f"Total Sales: ₹{metrics['total_sales']:,.2f}"),
                para(f"Total Profit: ₹{metrics['total_profit']:,.2f}"),
                para(f"Total Orders: {metrics['total_orders']:,}"),
                para(f"Total Customers: {metrics['total_customers']:,}"),
                para(f"Total Products: {metrics['total_products']:,}"),
                para(f"Profit Margin: {metrics['profit_margin']:.2f}%"),
                para(f"Average Order Value: ₹{metrics['average_order_value']:,.2f}"),
                para("Generated by DataKite AI.")
            ])
            document_xml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>" + body + "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"720\" w:right=\"720\" w:bottom=\"720\" w:left=\"720\"/></w:sectPr></w:body></w:document>"
            content_types="<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/></Types>"
            rels="<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/></Relationships>"
            word_rels="<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"></Relationships>"
            with _zf.ZipFile(out, "w", _zf.ZIP_DEFLATED) as z:
                z.writestr("[Content_Types].xml", content_types)
                z.writestr("_rels/.rels", rels)
                z.writestr("word/document.xml", document_xml)
                z.writestr("word/_rels/document.xml.rels", word_rels)
            out.seek(0)
            return send_file(out, as_attachment=True, download_name="Business_Analytics_Report.docx", mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        except Exception as fallback_exc:
            print("❌ WORD EXPORT FAILED:", repr(fallback_exc))
            return jsonify({"error": "Word export could not be generated.", "details": str(exc)}), 500

# ==========================================================
# 📊 PROFESSIONAL POWERPOINT REPORT
# ==========================================================

@app.route("/ppt/download", methods=["GET", "POST"])
def ppt_download():
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor as PptxRGBColor
    from pptx.chart.data import ChartData
    from pptx.enum.chart import XL_CHART_TYPE
    data = _restore_dataset_from_request()


    if data is None or data.empty:
        return jsonify({
            "error": "Please upload a CSV or Excel file first."
        }), 400
    

    data = data.copy()
    data.columns = data.columns.astype(str).str.strip()
    schema = universal_schema(data)
    metrics = _export_metrics(data, schema)
    total_sales = metrics["total_sales"]
    total_profit = metrics["total_profit"]
    total_quantity = metrics["total_quantity"]
    total_orders = metrics["total_orders"]
    total_customers = metrics["total_customers"]
    total_products = metrics["total_products"]
    profit_margin = metrics["profit_margin"]
    average_order_value = metrics["average_order_value"]

    # Universal export aliases: map common business concepts to the
    # generator's internal names so real-world headers are accepted.
    export_map = {
        "Amount": schema.get("sales"),
        "Profit": schema.get("profit"),
        "Quantity": schema.get("quantity"),
        "Customer": schema.get("customer"),
        "Product": schema.get("product"),
        "City": schema.get("city"),
        "Category": schema.get("category"),
        "Date": schema.get("date"),
        "Payment": schema.get("payment"),
        "Status": schema.get("status"),
    }
    for canonical, source in export_map.items():
        if source and source in data.columns and canonical not in data.columns:
            data[canonical] = data[source]

    if "Amount" not in data.columns:
        return jsonify({"error": "No usable sales/revenue/amount field was detected in this dataset."}), 400
    for col in ["Profit", "Quantity"]:
        if col not in data.columns:
            data[col] = 0
    for col in ["Customer", "Product"]:
        if col not in data.columns:
            data[col] = pd.Series([None] * len(data), index=data.index)

    for col in ["Amount", "Profit", "Quantity"]:
        data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0)

    def money(value):
        return f"₹{float(value):,.2f}"

    # ------------------------------------------------------
    # PPT setup
    # ------------------------------------------------------

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    GREEN = PptxRGBColor(22, 163, 74)
    DARK_GREEN = PptxRGBColor(22, 101, 52)
    DARK = PptxRGBColor(31, 41, 55)
    WHITE = PptxRGBColor(255, 255, 255)

    blank_layout = prs.slide_layouts[6]

    def add_title(slide, title):
        box = slide.shapes.add_textbox(
            Inches(0.6),
            Inches(0.35),
            Inches(12),
            Inches(0.6)
        )

        p = box.text_frame.paragraphs[0]
        run = p.add_run()
        run.text = title
        run.font.size = Pt(26)
        run.font.bold = True
        run.font.color.rgb = DARK_GREEN

    def add_text(slide, text, x, y, w, h,
                 size=18, bold=False):

        box = slide.shapes.add_textbox(
            Inches(x),
            Inches(y),
            Inches(w),
            Inches(h)
        )

        tf = box.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = str(text)
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = DARK

        return box

    def add_kpi(slide, title, value, x, y):

        shape = slide.shapes.add_shape(
            1,
            Inches(x),
            Inches(y),
            Inches(2.7),
            Inches(1.35)
        )

        shape.fill.solid()
        shape.fill.fore_color.rgb = WHITE

        shape.line.color.rgb = GREEN

        tf = shape.text_frame
        tf.clear()

        p = tf.paragraphs[0]
        p.alignment = 1

        r = p.add_run()
        r.text = str(value)
        r.font.size = Pt(23)
        r.font.bold = True
        r.font.color.rgb = DARK_GREEN

        p2 = tf.add_paragraph()
        p2.alignment = 1

        r2 = p2.add_run()
        r2.text = title
        r2.font.size = Pt(11)
        r2.font.color.rgb = DARK

    # ------------------------------------------------------
    # 1. COVER
    # ------------------------------------------------------

    slide = prs.slides.add_slide(blank_layout)

    add_text(
        slide,
        "BUSINESS ANALYTICS",
        0.8, 2.1, 11.8, 0.8,
        34, True
    )

    add_text(
        slide,
        "Professional Sales & Customer Analytics",
        0.8, 3.0, 11.8, 0.6,
        20
    )

    add_text(
        slide,
        "Generated by Data Analyst AI Assistant",
        0.8, 5.7, 11.8, 0.5,
        12
    )

    # ------------------------------------------------------
    # 2. KPI DASHBOARD
    # ------------------------------------------------------

    slide = prs.slides.add_slide(blank_layout)

    add_title(slide, "Business Performance Overview")

    add_kpi(
        slide, "Total Sales",
        money(total_sales), 0.6, 1.4
    )

    add_kpi(
        slide, "Total Profit",
        money(total_profit), 3.5, 1.4
    )

    add_kpi(
        slide, "Orders",
        f"{total_orders:,}", 6.4, 1.4
    )

    add_kpi(
        slide, "Customers",
        f"{total_customers:,}", 9.3, 1.4
    )

    add_kpi(
        slide, "Products",
        f"{total_products:,}", 0.6, 3.2
    )

    add_kpi(
        slide, "Quantity",
        f"{total_quantity:,}", 3.5, 3.2
    )

    add_kpi(
        slide, "Profit Margin",
        f"{profit_margin:.2f}%", 6.4, 3.2
    )

    add_kpi(
        slide, "Avg Order Value",
        money(average_order_value), 9.3, 3.2
    )

    # ------------------------------------------------------
    # 3. TOP PRODUCTS
    # ------------------------------------------------------

    top_products = (
        data.groupby("Product")["Amount"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    slide = prs.slides.add_slide(blank_layout)

    add_title(slide, "Top 10 Products by Sales")

    rows = 11
    cols = 3

    table = slide.shapes.add_table(
        rows,
        cols,
        Inches(0.7),
        Inches(1.3),
        Inches(11.9),
        Inches(5.5)
    ).table

    headers = ["Rank", "Product", "Sales"]

    for i, header in enumerate(headers):
        table.cell(0, i).text = header

    for i, (product, sales) in enumerate(
        top_products.items(),
        start=1
    ):
        table.cell(i, 0).text = str(i)
        table.cell(i, 1).text = str(product)
        table.cell(i, 2).text = money(sales)

    # ------------------------------------------------------
    # 4. CITY ANALYSIS
    # ------------------------------------------------------

    if "City" in data.columns:

        city_sales = (
            data.groupby("City")["Amount"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
        )

        slide = prs.slides.add_slide(blank_layout)

        add_title(slide, "Top Cities by Sales")

        table = slide.shapes.add_table(
            11,
            3,
            Inches(0.7),
            Inches(1.3),
            Inches(11.9),
            Inches(5.5)
        ).table

        for i, header in enumerate(
            ["Rank", "City", "Sales"]
        ):
            table.cell(0, i).text = header

        for i, (city, sales) in enumerate(
            city_sales.items(),
            start=1
        ):
            table.cell(i, 0).text = str(i)
            table.cell(i, 1).text = str(city)
            table.cell(i, 2).text = money(sales)
    # ------------------------------------------------------
    # 4.1 CITY SALES CHART
    # ------------------------------------------------------

    if "City" in data.columns:

        city_chart_data = (
            data.groupby("City")["Amount"]
            .sum()
            .sort_values(
                ascending=False
            )
            .head(10)
        )

        if not city_chart_data.empty:

            slide = prs.slides.add_slide(
                blank_layout
            )

            add_title(
                slide,
                "Top 10 Cities by Sales"
            )

            chart_data = ChartData()

            chart_data.categories = [
                str(city)
                for city in city_chart_data.index
            ]

            chart_data.add_series(
                "Sales",
                [
                    float(value)
                    for value in city_chart_data.values
                ]
            )

            chart = slide.shapes.add_chart(
                XL_CHART_TYPE.BAR_CLUSTERED,
                Inches(0.8),
                Inches(1.3),
                Inches(11.7),
                Inches(5.5),
                chart_data
            ).chart

            chart.has_legend = False
            chart.has_title = False
    # ------------------------------------------------------
    # 5. MONTHLY SALES
    # ------------------------------------------------------

    if "Date" in data.columns:

        temp = data.copy()

        temp["Date"] = pd.to_datetime(
            temp["Date"],
            errors="coerce"
        )

        temp = temp.dropna(
            subset=["Date"]
        )

        if not temp.empty:

            monthly_sales = (
                temp.groupby(
                    temp["Date"].dt.to_period("M")
                )["Amount"]
                .sum()
                .sort_index()
            )

            if not monthly_sales.empty:
  
                slide = prs.slides.add_slide(
                    blank_layout
                )

                add_title(
                    slide,
                    "Monthly Sales Performance"
                )

                chart_data = ChartData()

                chart_data.categories = [
                    str(x)
                    for x in monthly_sales.index
                ]

                chart_data.add_series(
                    "Sales",
                    [
                        float(value)
                        for value in monthly_sales.values
                    ]
                )

                chart = slide.shapes.add_chart(
                    XL_CHART_TYPE.COLUMN_CLUSTERED,
                    Inches(0.8),
                    Inches(1.3),
                    Inches(11.7),
                    Inches(5.5),
                    chart_data
                ).chart

                chart.has_legend = False
                chart.has_title = False

    # ------------------------------------------------------
    # 5.1 MONTHLY PROFIT
    # ------------------------------------------------------

    if "Date" in data.columns:

        temp = data.copy()

        temp["Date"] = pd.to_datetime(
            temp["Date"],
            errors="coerce"
        )

        temp = temp.dropna(
            subset=["Date"]
        )

        if not temp.empty:

            monthly_profit = (
                temp.groupby(
                    temp["Date"].dt.to_period("M")
                )["Profit"]
                .sum()
                .sort_index()
            )

            if not monthly_profit.empty:

                slide = prs.slides.add_slide(
                    blank_layout
                )

                add_title(
                    slide,
                    "Monthly Profit Performance"
                )

                chart_data = ChartData()

                chart_data.categories = [
                    str(x)
                    for x in monthly_profit.index
                ]

                chart_data.add_series(
                    "Profit",
                    [
                        float(value)
                        for value in monthly_profit.values
                    ]
                )

                chart = slide.shapes.add_chart(
                    XL_CHART_TYPE.LINE,
                    Inches(0.8),
                    Inches(1.3),
                    Inches(11.7),
                    Inches(5.5),
                    chart_data
                ).chart

                chart.has_legend = False
                chart.has_title = False
    # ------------------------------------------------------
    # 6. PAYMENT ANALYSIS
    # ------------------------------------------------------

    payment_column = None

    if "Payment" in data.columns:
 
        payment_column = "Payment"

    elif "Payment Method" in data.columns:

        payment_column = "Payment Method"

    if payment_column:

        payment_sales = (
            data.groupby(payment_column)["Amount"]
            .sum()
            .sort_values(ascending=False)
        )

        slide = prs.slides.add_slide(
            blank_layout
        )

        add_title(
            slide,
            "Sales by Payment Method"
        )

        chart_data = ChartData()

        chart_data.categories = [
            str(method)
            for method in payment_sales.index
        ]

        chart_data.add_series(
            "Sales",
            [
                float(value)
                for value in payment_sales.values
            ]
        )

        chart = slide.shapes.add_chart(
        
            XL_CHART_TYPE.COLUMN_CLUSTERED,
            Inches(0.8),
            Inches(1.3),
            Inches(11.7),
            Inches(5.5),
            chart_data
        ).chart

        chart.has_legend = False
        chart.has_title = False
    # ------------------------------------------------------
    # 7. INSIGHTS
    # ------------------------------------------------------

    slide = prs.slides.add_slide(blank_layout)

    add_title(slide, "Key Business Insights")

    insights = []

    if not top_products.empty:
        insights.append(
            f"• {top_products.index[0]} is the highest-sales product."
        )

    if "City" in data.columns and not city_sales.empty:
        insights.append(
            f"• {city_sales.index[0]} is the strongest city by sales."
        )

    insights.extend([
        f"• Total sales: {money(total_sales)}",
        f"• Total profit: {money(total_profit)}",
        f"• Profit margin: {profit_margin:.2f}%",
        f"• Total orders: {total_orders:,}",
        f"• Total customers: {total_customers:,}"
    ])

    add_text(
        slide,
        "\n".join(insights),
        1.0, 1.5, 11.0, 4.8,
        20
    )

    # ------------------------------------------------------
    # 8. RECOMMENDATIONS
    # ------------------------------------------------------

    slide = prs.slides.add_slide(blank_layout)

    add_title(slide, "Business Recommendations")

    recommendations = [
        "Maintain sufficient inventory for high-performing products.",
        "Develop retention strategies for high-value customers.",
        "Monitor city-level performance.",
        "Track monthly sales and profit trends.",
        "Review products with high sales but low profit.",
        "Evaluate payment-method performance.",
        "Use analytics to guide future decisions."
    ]

    add_text(
        slide,
        "\n".join(
            "• " + x for x in recommendations
        ),
        1.0, 1.4, 11.2, 5.2,
        18
    )

    # ------------------------------------------------------
    # SAVE
    # ------------------------------------------------------
     
    
    # Vercel source directories are read-only; all generated files must go
    # to the writable production scratch directory.
    output_path = os.path.join(
        UPLOAD_FOLDER,
        "Business_Analytics_Report.pptx"
    )

    prs.save(output_path)

    print(
        "✅ Professional PowerPoint generated:",
        output_path
    )

    return send_file(
        output_path,
        as_attachment=True,
        download_name="Business_Analytics_Report.pptx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        )
    ) 
@app.route("/upload-excel", methods=["POST"])
def upload_excel():

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please select an Excel file."
        }), 400

    upload_folder = os.path.join(
        os.path.dirname(__file__),
        "..",
        "uploads"
    )

    os.makedirs(upload_folder, exist_ok=True)

    excel_path = os.path.join(
        upload_folder,
        file.filename
    )

    file.save(excel_path)

    return jsonify({
        "filename": file.filename,
        "message": "✅ Excel file uploaded successfully!"
    })
# ==========================================================
# 🔄 PHASE 4.2 — WORD → PDF
# ==========================================================

@app.route("/convert/word-to-pdf", methods=["POST"])
def convert_word_to_pdf():

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload a Word file."
        }), 400

    if not file.filename.lower().endswith(".docx"):
        return jsonify({
            "error": "Please upload a .docx Word file."
        }), 400

    upload_folder = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "uploads"
        )
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    input_path = os.path.join(
        upload_folder,
        file.filename
    )

    output_name = (
        os.path.splitext(file.filename)[0]
        + ".pdf"
    )

    output_path = os.path.join(
        upload_folder,
        output_name
    )

    file.save(input_path)

    try:

        # Cross-platform LibreOffice detection (Linux/Mac PATH first,
        # then common Windows install location as a fallback).
        libreoffice = (
            shutil.which("soffice")
            or shutil.which("libreoffice")
        )

        if not libreoffice:

            windows_fallback = (
                r"C:\Program Files\LibreOffice\program\soffice.exe"
            )

            if os.path.exists(windows_fallback):
                libreoffice = windows_fallback

        if not libreoffice:

            return jsonify({
                "error": "LibreOffice executable was not found."
            }), 500

        result = subprocess.run(
            [
                libreoffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                upload_folder,
                input_path
            ],
            check=True,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:

            return jsonify({
                "error": (
                    "Word to PDF conversion failed: "
                    + str(result.stderr)
                )
            }), 500

        if not os.path.exists(output_path):

            return jsonify({
                "error": "PDF file was not created."
            }), 500

        print(
            "✅ Word → PDF generated:",
            output_path
        )

        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_name,
            mimetype="application/pdf"
        )

    except Exception as error:

        print(
            "❌ Word → PDF error:",
            error
        )

        return jsonify({
            "error": str(error)
        }), 500
# ==========================================================
# 📕 PHASE 4.5 — PDF → WORD
# ==========================================================

@app.route("/convert/pdf-to-word", methods=["POST"])
def convert_pdf_to_word():
    import pymupdf

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload a PDF file."
        }), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({
            "error": "Please upload a PDF file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        output_name = (
            os.path.splitext(file.filename)[0]
            + ".docx"
        )

        output_path = os.path.join(
            upload_folder,
            output_name
        )

        # Save PDF
        file.save(input_path)

        # --------------------------------------------------
        # CHECK PDF PAGE COUNT
        # --------------------------------------------------

        # Check PDF page count
        doc = pymupdf.open(input_path)

        page_count = len(doc)

        print("📕 PDF pages:", page_count)

        doc.close()

        if page_count > 100:
            return jsonify({
                "error": f"PDF has {page_count} pages. PDF → Word conversion is limited to 100 pages."
            }), 400
        
        # --------------------------------------------------
        # PDF → WORD
        # --------------------------------------------------

        from pdf2docx import Converter

        converter = Converter(input_path)

        try:

            converter.convert(output_path)

        finally:

            converter.close()

        # --------------------------------------------------
        # CHECK OUTPUT
        # --------------------------------------------------

        if not os.path.exists(output_path):

            return jsonify({
                "error": "PDF → Word conversion failed."
            }), 500

        print(
            "✅ PDF → Word successful:",
            output_path
        )

        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_name,
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        )

    except Exception as e:

        print(
            "❌ PDF → WORD ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "PDF → Word conversion failed: "
                + str(e)
        }), 500
# ==========================================================
# 📊 PHASE 4.6 — PDF → EXCEL
# ==========================================================

@app.route("/convert/pdf-to-excel", methods=["POST"])
def convert_pdf_to_excel():
    from openpyxl import Workbook

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload a PDF file."
        }), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({
            "error": "Please upload a PDF file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        output_name = (
            os.path.splitext(file.filename)[0]
            + ".xlsx"
        )

        output_path = os.path.join(
            upload_folder,
            output_name
        )

        # Save PDF
        file.save(input_path)

        # --------------------------------------------------
        # PDF → EXCEL
        # --------------------------------------------------

        import pdfplumber
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "PDF Data"

        with pdfplumber.open(input_path) as pdf:

            row_number = 1

            for page_number, page in enumerate(pdf.pages, start=1):

                tables = page.extract_tables()

                for table in tables:

                    for row in table:

                        if row:

                            cleaned_row = [
                                "" if cell is None
                                else str(cell).strip()
                                for cell in row
                            ]

                            for column_number, value in enumerate(
                                cleaned_row,
                                start=1
                            ):
                                worksheet.cell(
                                    row=row_number,
                                    column=column_number,
                                    value=value
                                )

                            row_number += 1

                    # Empty row between tables
                    row_number += 1

        workbook.save(output_path)

        # --------------------------------------------------
        # CHECK OUTPUT
        # --------------------------------------------------

        if not os.path.exists(output_path):

            return jsonify({
                "error": "PDF → Excel conversion failed."
            }), 500

        print(
            "✅ PDF → Excel successful:",
            output_path
        )

        return jsonify({
            "success": True,
            "message": "PDF → Excel conversion successful.",
            "filename": output_name,
            "download_url": "/uploads/" + output_name
        })

    except Exception as e:

        print(
            "❌ PDF → EXCEL ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "PDF → Excel conversion failed: "
                + str(e)
        }), 500
# ==========================================================
# 📕 PHASE 4.7 — PDF → POWERPOINT
# ==========================================================

@app.route("/convert/pdf-to-ppt", methods=["POST"])
def convert_pdf_to_ppt():
    from pptx import Presentation
    from pptx.util import Inches
    import pymupdf

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload a PDF file."
        }), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({
            "error": "Please upload a PDF file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        output_name = (
            os.path.splitext(file.filename)[0]
            + ".pptx"
        )

        output_path = os.path.join(
            upload_folder,
            output_name
        )

        file.save(input_path)

        # --------------------------------------------------
        # PDF → PPT
        # Each PDF page becomes one PowerPoint slide
        # --------------------------------------------------

        import pymupdf
        from pptx import Presentation
        from pptx.util import Inches

        pdf = pymupdf.open(input_path)

        prs = Presentation()

        # Remove default slide
        if len(prs.slides) > 0:
            rId = prs.slides._sldIdLst[0].rId
            prs.part.drop_rel(rId)
            del prs.slides._sldIdLst[0]

        # Standard 16:9 PPT
        prs.slide_width = Inches(13.333333)
        prs.slide_height = Inches(7.5)

        blank_layout = prs.slide_layouts[6]

        for page_number, page in enumerate(
            pdf,
            start=1
        ):

            print(
                f"📕 PDF → PPT page {page_number}"
            )

            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(1.5, 1.5),
                alpha=False
            )

            image_path = os.path.join(
                upload_folder,
                f"pdf_ppt_page_{page_number}.png"
            )

            pixmap.save(image_path)

            slide = prs.slides.add_slide(
                blank_layout
            )

            # Fill entire slide
            slide.shapes.add_picture(
                image_path,
                0,
                0,
                width=prs.slide_width,
                height=prs.slide_height
            )

            if os.path.exists(image_path):
                os.remove(image_path)

        pdf.close()

        prs.save(output_path)

        if not os.path.exists(output_path):
            return jsonify({
                "error": "PDF → PowerPoint conversion failed."
            }), 500

        print(
            "✅ PDF → PowerPoint successful:",
            output_path
        )

        return jsonify({
            "success": True,
            "message": "PDF → PowerPoint conversion successful.",
            "filename": output_name,
            "download_url": "/uploads/" + output_name
        })

    except Exception as e:

        print(
            "❌ PDF → PPT ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "PDF → PowerPoint conversion failed: "
                + str(e)
        }), 500        
# ==========================================================
# 📊 PHASE 4.3 — EXCEL → PDF
# ==========================================================

@app.route("/convert/excel-to-pdf", methods=["POST"])
def convert_excel_to_pdf():

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload an Excel file."
        }), 400

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({
            "error": "Please upload an Excel (.xlsx or .xls) file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        pdf_name = (
            os.path.splitext(file.filename)[0]
            + ".pdf"
        )

        pdf_path = os.path.join(
            upload_folder,
            pdf_name
        )

        # Save Excel
        file.save(input_path)

        # --------------------------------------------------
        # FIND LIBREOFFICE
        # --------------------------------------------------

        libreoffice = shutil.which("soffice")

        if not libreoffice:
            libreoffice = shutil.which("libreoffice")

        if not libreoffice:
            libreoffice = (
                r"C:\Program Files\LibreOffice\program\soffice.exe"
            )

        if not os.path.exists(libreoffice):
            return jsonify({
                "error": "LibreOffice was not found."
            }), 500

        print("LibreOffice:", libreoffice)
        print("Excel input:", input_path)
        print("PDF output:", pdf_path)

        # Remove old PDF if it exists
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        # --------------------------------------------------
        # CONVERT
        # --------------------------------------------------

        result = subprocess.run(
            [
                libreoffice,
                "--headless",
                "--convert-to",
                "pdf:calc_pdf_Export",
                "--outdir",
                upload_folder,
                input_path
            ],
            capture_output=True,
            text=True
        )

        print("LibreOffice stdout:")
        print(result.stdout)

        print("LibreOffice stderr:")
        print(result.stderr)

        # --------------------------------------------------
        # CHECK RESULT
        # --------------------------------------------------

        if result.returncode != 0:

            return jsonify({
                "error": "Excel → PDF conversion failed.",
                "details": (
                    result.stderr
                    or result.stdout
                    or "LibreOffice conversion failed."
                )
            }), 500

        if not os.path.exists(pdf_path):

            return jsonify({
                "error": "PDF file was not created.",
                "details": (
                    result.stderr
                    or result.stdout
                    or "Unknown LibreOffice error."
                )
            }), 500

        print(
            "✅ Excel → PDF successful:",
            pdf_path
        )

        return jsonify({
            "success": True,
            "message": "Excel → PDF conversion successful.",
            "filename": pdf_name,
            "download_url": "/uploads/" + pdf_name
        })

    except Exception as e:

        print(
            "❌ EXCEL → PDF ERROR:",
            repr(e)
        )

        return jsonify({
            "error": f"Excel → PDF conversion failed: {str(e)}"
        }), 500
# ==========================================================
# 📊 PHASE 4.4 — POWERPOINT → PDF
# ==========================================================
@app.route("/convert/powerpoint-to-pdf", methods=["POST"])
def convert_powerpoint_to_pdf():

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload a PowerPoint file."
        }), 400

    if not file.filename.lower().endswith((".pptx", ".ppt")):
        return jsonify({
            "error": "Please upload a PowerPoint (.pptx or .ppt) file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(
            upload_folder,
            exist_ok=True
        )

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        file.save(input_path)

        # --------------------------------------------------
        # FIND LIBREOFFICE
        # --------------------------------------------------

        libreoffice = shutil.which("libreoffice")

        if not libreoffice:
            libreoffice = shutil.which("soffice")

        if not libreoffice:
            libreoffice = r"C:\Program Files\LibreOffice\program\soffice.exe"

        if not os.path.exists(libreoffice):
            return jsonify({
                "error": "LibreOffice was not found."
            }), 500

        # --------------------------------------------------
        # CONVERT POWERPOINT → PDF
        # --------------------------------------------------

        result = subprocess.run(
            [
                libreoffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                upload_folder,
                input_path
            ],
            check=True,
            capture_output=True,
            text=True
        )

        pdf_name = os.path.splitext(
            file.filename
        )[0] + ".pdf"

        pdf_path = os.path.join(
            upload_folder,
            pdf_name
        )

        if not os.path.exists(pdf_path):

            return jsonify({
                "error": "PowerPoint to PDF conversion failed.",
                "details": result.stderr
            }), 500

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=pdf_name,
            mimetype="application/pdf"
        )

    except Exception as e:

        print(
            "❌ POWERPOINT → PDF ERROR:",
            e
        )

        return jsonify({
            "error": f"PowerPoint to PDF conversion failed: {str(e)}"
        }), 500
# ==========================================================
# 📊 PHASE 4.8 — EXCEL → WORD
# ==========================================================

@app.route("/convert/excel-to-word", methods=["POST"])
def convert_excel_to_word():
    from docx import Document

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload an Excel file."
        }), 400

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({
            "error": "Please upload an Excel (.xlsx or .xls) file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        output_name = (
            os.path.splitext(file.filename)[0]
            + ".docx"
        )

        output_path = os.path.join(
            upload_folder,
            output_name
        )

        # Save Excel
        file.save(input_path)

        # --------------------------------------------------
        # EXCEL → WORD
        # --------------------------------------------------

        excel_file = pd.ExcelFile(input_path)

        document = Document()

        document.add_heading(
            os.path.splitext(file.filename)[0],
            level=1
        )

        for sheet_name in excel_file.sheet_names:

            data = pd.read_excel(
                input_path,
                sheet_name=sheet_name
            )

            document.add_heading(
                sheet_name,
                level=2
            )

            if data.empty:
                document.add_paragraph(
                    "No data found in this sheet."
                )
                continue

            table = document.add_table(
                rows=1,
                cols=len(data.columns)
            )

            table.style = "Table Grid"

            # Header
            header_cells = table.rows[0].cells

            for column_number, column_name in enumerate(
                data.columns
            ):
                header_cells[column_number].text = str(
                    column_name
                )

            # Data
            for _, row in data.iterrows():

                cells = table.add_row().cells

                for column_number, value in enumerate(row):

                    if pd.isna(value):
                        value = ""

                    cells[column_number].text = str(value)

            document.add_paragraph()

        document.save(output_path)

        # --------------------------------------------------
        # CHECK OUTPUT
        # --------------------------------------------------

        if not os.path.exists(output_path):

            return jsonify({
                "error": "Excel → Word conversion failed."
            }), 500

        print(
            "✅ Excel → Word successful:",
            output_path
        )

        return jsonify({
            "success": True,
            "message": "Excel → Word conversion successful.",
            "filename": output_name,
            "download_url": "/uploads/" + output_name
        })

    except Exception as e:

        print(
            "❌ EXCEL → WORD ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "Excel → Word conversion failed: "
                + str(e)
        }), 500
# ==========================================================
# 📊 PHASE 4.9 — EXCEL → POWERPOINT
# ==========================================================

@app.route("/convert/excel-to-pptx", methods=["POST"])
def convert_excel_to_pptx():
    from pptx import Presentation
    from pptx.util import Inches, Pt

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload an Excel file."
        }), 400

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({
            "error": "Please upload an Excel (.xlsx or .xls) file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        output_name = (
            os.path.splitext(file.filename)[0]
            + ".pptx"
        )

        output_path = os.path.join(
            upload_folder,
            output_name
        )

        file.save(input_path)

        # --------------------------------------------------
        # EXCEL → POWERPOINT
        # --------------------------------------------------

        from pptx import Presentation
        from pptx.util import Inches, Pt

        excel_file = pd.ExcelFile(input_path)

        prs = Presentation()

        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        blank_layout = prs.slide_layouts[6]

        for sheet_name in excel_file.sheet_names:

            data = pd.read_excel(
                input_path,
                sheet_name=sheet_name
            )

            slide = prs.slides.add_slide(
                blank_layout
            )

            # Title
            title_box = slide.shapes.add_textbox(
                Inches(0.5),
                Inches(0.3),
                Inches(12.3),
                Inches(0.6)
            )

            title_frame = title_box.text_frame
            title_frame.text = sheet_name

            title_frame.paragraphs[0].font.size = Pt(24)
            title_frame.paragraphs[0].font.bold = True

            if data.empty:
                continue

            # Limit columns for readable slide
            data = data.iloc[:, :10]

            rows = min(len(data), 20) + 1
            cols = len(data.columns)

            table_shape = slide.shapes.add_table(
                rows,
                cols,
                Inches(0.4),
                Inches(1.2),
                Inches(12.5),
                Inches(5.7)
            )

            table = table_shape.table

            # Header
            for col_index, column in enumerate(data.columns):

                cell = table.cell(
                    0,
                    col_index
                )

                cell.text = str(column)

                for paragraph in cell.text_frame.paragraphs:
                    paragraph.font.bold = True
                    paragraph.font.size = Pt(11)

            # Data
            for row_index, (_, row) in enumerate(
                data.head(20).iterrows(),
                start=1
            ):

                for col_index, value in enumerate(row):

                    if pd.isna(value):
                        value = ""

                    cell = table.cell(
                        row_index,
                        col_index
                    )

                    cell.text = str(value)

                    for paragraph in cell.text_frame.paragraphs:
                        paragraph.font.size = Pt(9)

        prs.save(output_path)

        if not os.path.exists(output_path):

            return jsonify({
                "error": "Excel → PowerPoint conversion failed."
            }), 500

        print(
            "✅ Excel → PowerPoint successful:",
            output_path
        )

        return jsonify({
            "success": True,
            "message": "Excel → PowerPoint conversion successful.",
            "filename": output_name,
            "download_url": "/uploads/" + output_name
        })

    except Exception as e:

        print(
            "❌ EXCEL → PPTX ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "Excel → PowerPoint conversion failed: "
                + str(e)
        }), 500
# ==========================================================
# 📊 PHASE 4.10 — POWERPOINT → WORD
# ==========================================================

@app.route("/convert/pptx-to-word", methods=["POST"])
def convert_pptx_to_word():
    from docx import Document
    from pptx import Presentation

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload a PowerPoint file."
        }), 400

    if not file.filename.lower().endswith((".pptx", ".ppt")):
        return jsonify({
            "error": "Please upload a PowerPoint (.pptx or .ppt) file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        output_name = (
            os.path.splitext(file.filename)[0]
            + ".docx"
        )

        output_path = os.path.join(
            upload_folder,
            output_name
        )

        file.save(input_path)

        # --------------------------------------------------
        # POWERPOINT → WORD
        # --------------------------------------------------

        prs = Presentation(input_path)

        document = Document()

        document.add_heading(
            os.path.splitext(file.filename)[0],
            level=1
        )

        for slide_number, slide in enumerate(
            prs.slides,
            start=1
        ):

            document.add_heading(
                f"Slide {slide_number}",
                level=2
            )

            for shape in slide.shapes:

                if not hasattr(shape, "text"):
                    continue

                text = shape.text.strip()

                if not text:
                    continue

                paragraph = document.add_paragraph()

                paragraph.add_run(
                    text
                )

            document.add_paragraph()

        document.save(output_path)

        # --------------------------------------------------
        # CHECK OUTPUT
        # --------------------------------------------------

        if not os.path.exists(output_path):

            return jsonify({
                "error": "PowerPoint → Word conversion failed."
            }), 500

        print(
            "✅ PowerPoint → Word successful:",
            output_path
        )

        return jsonify({
            "success": True,
            "message": "PowerPoint → Word conversion successful.",
            "filename": output_name,
            "download_url": "/uploads/" + output_name
        })

    except Exception as e:

        print(
            "❌ PPTX → WORD ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "PowerPoint → Word conversion failed: "
                + str(e)
        }), 500
# ==========================================================
# 📊 PHASE 4.11 — POWERPOINT → EXCEL
# ==========================================================

@app.route("/convert/pptx-to-excel", methods=["POST"])
def convert_pptx_to_excel():
    from pptx import Presentation
    from openpyxl import Workbook

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload a PowerPoint file."
        }), 400

    if not file.filename.lower().endswith((".pptx", ".ppt")):
        return jsonify({
            "error": "Please upload a PowerPoint (.pptx or .ppt) file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        output_name = (
            os.path.splitext(file.filename)[0]
            + ".xlsx"
        )

        output_path = os.path.join(
            upload_folder,
            output_name
        )

        file.save(input_path)

        # --------------------------------------------------
        # POWERPOINT → EXCEL
        # --------------------------------------------------

        prs = Presentation(input_path)

        workbook = Workbook()

        # Remove default sheet
        worksheet = workbook.active
        worksheet.title = "PPT Data"

        row_number = 1

        for slide_number, slide in enumerate(
            prs.slides,
            start=1
        ):

            # Slide heading
            worksheet.cell(
                row=row_number,
                column=1,
                value=f"Slide {slide_number}"
            )

            row_number += 1

            for shape in slide.shapes:

                # Text
                if hasattr(shape, "text"):

                    text = shape.text.strip()

                    if text:

                        worksheet.cell(
                            row=row_number,
                            column=1,
                            value=text
                        )

                        row_number += 1

                # Tables
                if shape.has_table:

                    table = shape.table

                    for table_row in table.rows:

                        values = []

                        for cell in table_row.cells:
                            values.append(
                                cell.text.strip()
                            )

                        for column_number, value in enumerate(
                            values,
                            start=1
                        ):

                            worksheet.cell(
                                row=row_number,
                                column=column_number,
                                value=value
                            )

                        row_number += 1

                    row_number += 1

            row_number += 1

        # --------------------------------------------------
        # SAVE EXCEL
        # --------------------------------------------------

        workbook.save(output_path)

        if not os.path.exists(output_path):

            return jsonify({
                "error": "PowerPoint → Excel conversion failed."
            }), 500

        print(
            "✅ PowerPoint → Excel successful:",
            output_path
        )

        return jsonify({
            "success": True,
            "message": "PowerPoint → Excel conversion successful.",
            "filename": output_name,
            "download_url": "/uploads/" + output_name
        })

    except Exception as e:

        print(
            "❌ PPTX → EXCEL ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "PowerPoint → Excel conversion failed: "
                + str(e)
        }), 500
# ==========================================================
# 📊 PHASE 4.12 — WORD → EXCEL
# ==========================================================

@app.route("/convert/word-to-excel", methods=["POST"])
def convert_word_to_excel():
    from docx import Document
    from openpyxl import Workbook

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload a Word file."
        }), 400

    if not file.filename.lower().endswith(".docx"):
        return jsonify({
            "error": "Please upload a .docx Word file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        output_name = (
            os.path.splitext(file.filename)[0]
            + ".xlsx"
        )

        output_path = os.path.join(
            upload_folder,
            output_name
        )

        file.save(input_path)

        # --------------------------------------------------
        # WORD → EXCEL
        # --------------------------------------------------

        document = Document(input_path)

        workbook = Workbook()

        worksheet = workbook.active
        worksheet.title = "Word Data"

        row_number = 1

        # --------------------------------------------------
        # PARAGRAPHS
        # --------------------------------------------------

        for paragraph in document.paragraphs:

            text = paragraph.text.strip()

            if text:

                worksheet.cell(
                    row=row_number,
                    column=1,
                    value=text
                )

                row_number += 1

        # --------------------------------------------------
        # TABLES
        # --------------------------------------------------

        for table_number, table in enumerate(
            document.tables,
            start=1
        ):

            # Table heading
            worksheet.cell(
                row=row_number,
                column=1,
                value=f"Table {table_number}"
            )

            row_number += 1

            for table_row in table.rows:

                for column_number, cell in enumerate(
                    table_row.cells,
                    start=1
                ):

                    worksheet.cell(
                        row=row_number,
                        column=column_number,
                        value=cell.text.strip()
                    )

                row_number += 1

            # Empty row between tables
            row_number += 1

        # --------------------------------------------------
        # SAVE EXCEL
        # --------------------------------------------------

        workbook.save(output_path)

        if not os.path.exists(output_path):

            return jsonify({
                "error": "Word → Excel conversion failed."
            }), 500

        print(
            "✅ Word → Excel successful:",
            output_path
        )

        return jsonify({
            "success": True,
            "message": "Word → Excel conversion successful.",
            "filename": output_name,
            "download_url": "/uploads/" + output_name
        })

    except Exception as e:

        print(
            "❌ WORD → EXCEL ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "Word → Excel conversion failed: "
                + str(e)
        }), 500
# ==========================================================
# 📊 PHASE 4.13 — WORD → POWERPOINT
# ==========================================================

@app.route("/convert/word-to-pptx", methods=["POST"])
def convert_word_to_pptx():
    from docx import Document
    from pptx import Presentation
    from pptx.util import Inches, Pt

    file = request.files.get("file")

    if file:
        file.filename = secure_filename(file.filename)

    if not file:
        return jsonify({
            "error": "Please upload a Word file."
        }), 400

    if not file.filename.lower().endswith(".docx"):
        return jsonify({
            "error": "Please upload a .docx Word file."
        }), 400

    try:

        upload_folder = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "uploads"
            )
        )

        os.makedirs(upload_folder, exist_ok=True)

        input_path = os.path.join(
            upload_folder,
            file.filename
        )

        output_name = (
            os.path.splitext(file.filename)[0]
            + ".pptx"
        )

        output_path = os.path.join(
            upload_folder,
            output_name
        )

        file.save(input_path)

        # --------------------------------------------------
        # WORD → POWERPOINT
        # --------------------------------------------------

        document = Document(input_path)

        prs = Presentation()

        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

        blank_layout = prs.slide_layouts[6]

        paragraphs = [
            p.text.strip()
            for p in document.paragraphs
            if p.text.strip()
        ]

        # Create slides from paragraphs
        for i in range(0, len(paragraphs), 6):

            slide = prs.slides.add_slide(
                blank_layout
            )

            title_box = slide.shapes.add_textbox(
                Inches(0.6),
                Inches(0.4),
                Inches(12),
                Inches(0.7)
            )

            title_box.text_frame.text = (
                os.path.splitext(file.filename)[0]
            )

            title_box.text_frame.paragraphs[0].font.size = Pt(26)
            title_box.text_frame.paragraphs[0].font.bold = True

            body_box = slide.shapes.add_textbox(
                Inches(0.8),
                Inches(1.4),
                Inches(11.7),
                Inches(5.3)
            )

            text_frame = body_box.text_frame
            text_frame.word_wrap = True

            for text in paragraphs[i:i + 6]:

                paragraph = text_frame.add_paragraph()

                paragraph.text = text
                paragraph.font.size = Pt(18)

                paragraph.space_after = Pt(10)

        # If document has no paragraphs
        if not paragraphs:

            slide = prs.slides.add_slide(
                blank_layout
            )

            box = slide.shapes.add_textbox(
                Inches(1),
                Inches(2),
                Inches(11),
                Inches(2)
            )

            box.text_frame.text = (
                "Word document contains no readable paragraphs."
            )

            box.text_frame.paragraphs[0].font.size = Pt(24)

        prs.save(output_path)

        # --------------------------------------------------
        # CHECK OUTPUT
        # --------------------------------------------------

        if not os.path.exists(output_path):

            return jsonify({
                "error": "Word → PowerPoint conversion failed."
            }), 500

        print(
            "✅ Word → PowerPoint successful:",
            output_path
        )

        return jsonify({
            "success": True,
            "message": "Word → PowerPoint conversion successful.",
            "filename": output_name,
            "download_url": "/uploads/" + output_name
        })

    except Exception as e:

        print(
            "❌ WORD → PPTX ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "Word → PowerPoint conversion failed: "
                + str(e)
        }), 500                                                
# ==========================================================
# 📂 SERVE GENERATED FILES
# ==========================================================

@app.route("/uploads/<path:filename>")
def download_uploaded_file(filename):

    upload_folder = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "uploads"
        )
    )

    return send_from_directory(
        upload_folder,
        filename,
        as_attachment=True
    )                                      
if __name__ == "__main__":

    # SECURITY: debug mode must never be on in production — it
    # exposes the interactive Werkzeug debugger (arbitrary code
    # execution) to anyone who can trigger a 500 error. Defaults to
    # OFF; set FLASK_DEBUG=1 explicitly for local development only.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=debug_mode
    )
