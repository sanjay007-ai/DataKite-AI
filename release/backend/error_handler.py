# ============================================================
# 🔥 PHASE 5.7 — ERROR HANDLING ENGINE
# ============================================================
#
# Purpose:
# Convert technical Python/backend errors into clean,
# professional messages for the AI Assistant.
#
# ============================================================

import os
import pandas as pd


# ============================================================
# ERROR CATEGORIES
# ============================================================

ERROR_FILE_NOT_FOUND = "FILE_NOT_FOUND"
ERROR_EMPTY_FILE = "EMPTY_FILE"
ERROR_INVALID_FILE = "INVALID_FILE"
ERROR_MISSING_COLUMN = "MISSING_COLUMN"
ERROR_INVALID_DATA = "INVALID_DATA"
ERROR_INVALID_YEAR = "INVALID_YEAR"
ERROR_COMPARISON = "COMPARISON_ERROR"
ERROR_ROOT_CAUSE = "ROOT_CAUSE_ERROR"
ERROR_RECOMMENDATION = "RECOMMENDATION_ERROR"
ERROR_UNKNOWN = "UNKNOWN_ERROR"


# ============================================================
# PROFESSIONAL ERROR MESSAGE
# ============================================================

def format_error(error_type, message=None, details=None):

    messages = {

        ERROR_FILE_NOT_FOUND:
            "⚠️ Dataset file was not found. "
            "Please make sure the required CSV file is available.",

        ERROR_EMPTY_FILE:
            "⚠️ The uploaded CSV file is empty. "
            "Please upload a CSV containing valid business data.",

        ERROR_INVALID_FILE:
            "⚠️ The uploaded file could not be read. "
            "Please check that it is a valid CSV file.",

        ERROR_MISSING_COLUMN:
            "⚠️ Required data columns are missing from the dataset.",

        ERROR_INVALID_DATA:
            "⚠️ The dataset contains invalid or unreadable data.",

        ERROR_INVALID_YEAR:
            "⚠️ The requested year is invalid or unavailable.",

        ERROR_COMPARISON:
            "⚠️ I couldn't complete the comparison because "
            "the comparison data could not be processed.",

        ERROR_ROOT_CAUSE:
            "⚠️ I couldn't complete the root cause analysis "
            "because the required comparison data could not be processed.",

        ERROR_RECOMMENDATION:
            "⚠️ I couldn't generate business recommendations "
            "because the required analysis could not be completed.",

        ERROR_UNKNOWN:
            "⚠️ An unexpected error occurred while processing "
            "your request."
    }

    answer = messages.get(
        error_type,
        messages[ERROR_UNKNOWN]
    )

    if details:
        answer += f"\n\nDetails: {details}"

    elif message:
        answer += f"\n\nDetails: {message}"

    return answer


# ============================================================
# FILE VALIDATION
# ============================================================

def validate_file(file_path):

    if not file_path:

        return {
            "valid": False,
            "error_type": ERROR_FILE_NOT_FOUND,
            "message": format_error(
                ERROR_FILE_NOT_FOUND
            )
        }

    if not os.path.exists(file_path):

        return {
            "valid": False,
            "error_type": ERROR_FILE_NOT_FOUND,
            "message": format_error(
                ERROR_FILE_NOT_FOUND
            )
        }

    if not file_path.lower().endswith(".csv"):

        return {
            "valid": False,
            "error_type": ERROR_INVALID_FILE,
            "message": format_error(
                ERROR_INVALID_FILE
            )
        }

    try:

        data = pd.read_csv(file_path)

    except Exception as error:

        return {
            "valid": False,
            "error_type": ERROR_INVALID_FILE,
            "message": format_error(
                ERROR_INVALID_FILE,
                details=str(error)
            )
        }

    if data.empty:

        return {
            "valid": False,
            "error_type": ERROR_EMPTY_FILE,
            "message": format_error(
                ERROR_EMPTY_FILE
            )
        }

    return {
        "valid": True,
        "error_type": None,
        "message": "✅ File validation successful.",
        "rows": len(data),
        "columns": list(data.columns)
    }


# ============================================================
# COLUMN VALIDATION
# ============================================================

def validate_columns(
    data,
    required_columns
):

    if data is None:

        return {
            "valid": False,
            "error_type": ERROR_INVALID_DATA,
            "message": format_error(
                ERROR_INVALID_DATA
            )
        }

    actual_columns = {
        str(column).strip().lower()
        for column in data.columns
    }

    missing = []

    for column in required_columns:

        if str(column).strip().lower() not in actual_columns:

            missing.append(column)

    if missing:

        return {
            "valid": False,
            "error_type": ERROR_MISSING_COLUMN,
            "message": format_error(
                ERROR_MISSING_COLUMN,
                details=(
                    "Missing columns: "
                    + ", ".join(
                        map(str, missing)
                    )
                )
            ),
            "missing_columns": missing
        }

    return {
        "valid": True,
        "error_type": None,
        "message": "✅ Required columns are available.",
        "missing_columns": []
    }


# ============================================================
# DATA VALIDATION
# ============================================================

def validate_business_data(data):

    if data is None:

        return {
            "valid": False,
            "error_type": ERROR_INVALID_DATA,
            "message": format_error(
                ERROR_INVALID_DATA
            )
        }

    if data.empty:

        return {
            "valid": False,
            "error_type": ERROR_EMPTY_FILE,
            "message": format_error(
                ERROR_EMPTY_FILE
            )
        }

    required_columns = [
        "Amount",
        "Profit",
        "Quantity"
    ]

    column_check = validate_columns(
        data,
        required_columns
    )

    if not column_check["valid"]:

        return column_check

    return {
        "valid": True,
        "error_type": None,
        "message": "✅ Business data validation successful."
    }


# ============================================================
# YEAR VALIDATION
# ============================================================

def validate_year(year):

    year_string = str(year).strip()

    if not year_string.isdigit():

        return {
            "valid": False,
            "error_type": ERROR_INVALID_YEAR,
            "message": format_error(
                ERROR_INVALID_YEAR,
                details=f"Invalid year: {year}"
            )
        }

    year_value = int(year_string)

    if year_value < 2000 or year_value > 2100:

        return {
            "valid": False,
            "error_type": ERROR_INVALID_YEAR,
            "message": format_error(
                ERROR_INVALID_YEAR,
                details=f"Unsupported year: {year}"
            )
        }

    return {
        "valid": True,
        "error_type": None,
        "message": "✅ Year validation successful.",
        "year": year_value
    }


# ============================================================
# ENGINE ERROR HANDLER
# ============================================================

def handle_engine_error(
    engine,
    error
):

    engine = str(engine).lower()

    if "comparison" in engine:

        error_type = ERROR_COMPARISON

    elif "root" in engine:

        error_type = ERROR_ROOT_CAUSE

    elif (
        "recommend" in engine
        or "recommendation" in engine
    ):

        error_type = ERROR_RECOMMENDATION

    else:

        error_type = ERROR_UNKNOWN

    return format_error(
        error_type,
        details=str(error)
    )


# ============================================================
# SAFE EXECUTION WRAPPER
# ============================================================

def safe_execute(
    function,
    *args,
    engine="engine",
    **kwargs
):

    try:

        result = function(
            *args,
            **kwargs
        )

        return {
            "success": True,
            "result": result,
            "error": None
        }

    except FileNotFoundError as error:

        return {
            "success": False,
            "result": None,
            "error": format_error(
                ERROR_FILE_NOT_FOUND,
                details=str(error)
            )
        }

    except pd.errors.EmptyDataError as error:

        return {
            "success": False,
            "result": None,
            "error": format_error(
                ERROR_EMPTY_FILE,
                details=str(error)
            )
        }

    except pd.errors.ParserError as error:

        return {
            "success": False,
            "result": None,
            "error": format_error(
                ERROR_INVALID_FILE,
                details=str(error)
            )
        }

    except Exception as error:

        return {
            "success": False,
            "result": None,
            "error": handle_engine_error(
                engine,
                error
            )
        }


# ============================================================
# QUICK ERROR CHECK
# ============================================================

def is_error(result):

    return (
        isinstance(result, dict)
        and result.get("success") is False
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "\n===== PHASE 5.7 ERROR HANDLING ENGINE =====\n"
    )

    print(
        format_error(
            ERROR_FILE_NOT_FOUND
        )
    )

    print()

    print(
        format_error(
            ERROR_MISSING_COLUMN,
            details="Missing columns: Amount, Profit"
        )
    )

    print()

    print(
        format_error(
            ERROR_COMPARISON,
            details="Comparison engine failed."
        )
    )

    print()

    print(
        "✅ PHASE 5.7 ERROR HANDLING ENGINE READY"
    )