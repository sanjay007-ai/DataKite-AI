"""Shared upload parsing pipeline.

Keeps file parsing independent from Flask so the exact same pipeline can be
unit-tested locally and used by the HTTP upload route.
"""
import os
import pandas as pd
from file_reader import read_file

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".pdf", ".docx", ".pptx"}


def parse_uploaded_file(path: str, display_name: str | None = None):
    name = display_name or os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return {"accepted": False, "error_code": "UNSUPPORTED_TYPE", "message": f"{name}: unsupported file type."}
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return {"accepted": False, "error_code": "EMPTY_FILE", "message": f"{name}: the uploaded file is empty."}

    try:
        result = read_file(path)
        if not isinstance(result, dict):
            raise ValueError("Reader returned an invalid result.")

        df = result.get("data")
        if isinstance(df, pd.DataFrame) and not df.empty:
            df = df.copy()
            df.columns = [str(c).strip() for c in df.columns]
            df["__source_file"] = name
            return {
                "accepted": True,
                "data": df,
                "reader_type": result.get("type", "dataset"),
                "format": result.get("format", ext.lstrip(".")),
                "rows": len(df),
                "columns": len(df.columns),
                "message": f"{name}: loaded {len(df):,} rows × {len(df.columns):,} columns.",
            }

        text = str(result.get("text") or "").strip()
        if text:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines:
                text_df = pd.DataFrame({"Document_Text": lines})
                text_df["__source_file"] = name
                return {
                    "accepted": True,
                    "data": text_df,
                    "reader_type": result.get("type", "document"),
                    "format": result.get("format", ext.lstrip(".")),
                    "rows": len(text_df),
                    "columns": len(text_df.columns),
                    "message": f"{name}: loaded document text ({len(text_df):,} rows).",
                    "text_fallback": True,
                }

        return {"accepted": False, "error_code": "NO_USABLE_DATA", "message": f"{name}: no readable table or text was detected."}
    except Exception as exc:
        return {"accepted": False, "error_code": "READ_FAILED", "message": f"{name}: {exc}"}
