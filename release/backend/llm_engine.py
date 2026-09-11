"""Optional real LLM layer for DataKite AI.

Uses Google's Gemini Developer API when GEMINI_API_KEY is configured.
Without a key, DataKite continues using its deterministic analytics engines.
"""
import os


def llm_enabled():
    return bool(os.environ.get("GEMINI_API_KEY"))


def ask_real_ai(question, data):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
    except Exception as exc:
        print("LLM SDK unavailable:", repr(exc))
        return None

    try:
        client = genai.Client(api_key=api_key)
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
        profile = _profile(data)
        prompt = f"""You are DataKite AI, a business analytics assistant.

Use the supplied dataset profile as evidence. Never invent values. If a value is not present, say so.
Answer clearly and concisely for a business user. Use bullets when useful.

DATASET PROFILE:
{profile}

USER QUESTION:
{question}

Return the best business answer."""
        response = client.models.generate_content(model=model, contents=prompt)
        text = getattr(response, "text", None)
        return text.strip() if text else None
    except Exception as exc:
        print("LLM request failed; using analytics fallback:", repr(exc))
        return None


def _profile(data):
    if data is None or getattr(data, "empty", True):
        return "No dataset is loaded."
    lines = [f"Rows: {len(data):,}", f"Columns: {len(data.columns):,}"]
    lines.append("Columns: " + ", ".join(map(str, data.columns[:80])))
    for col in data.select_dtypes(include="number").columns[:12]:
        series = data[col].dropna()
        if not series.empty:
            lines.append(f"{col}: sum={series.sum():,.2f}; avg={series.mean():,.2f}; min={series.min():,.2f}; max={series.max():,.2f}")
    for col in data.select_dtypes(include=["object", "string", "category"]).columns[:8]:
        vals = data[col].dropna().astype(str)
        if not vals.empty:
            top = vals.value_counts().head(5).to_dict()
            lines.append(f"{col} top values: {top}")
    return "\n".join(lines)
