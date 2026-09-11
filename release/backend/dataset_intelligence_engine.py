# ============================================================
# 🚧 PHASE 6.1 — DATASET INTELLIGENCE ENGINE
# ============================================================
#
# Features:
#   • Automatic dataset detection
#   • Column classification
#   • Dynamic KPI generation
#   • Numeric analysis
#   • Categorical analysis
#   • Date detection
#   • Dataset profiling
#
# ============================================================

import pandas as pd
import numpy as np


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_columns(df):

    df = df.copy()

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    return df


def is_numeric(series):

    return pd.api.types.is_numeric_dtype(series)


def try_numeric(series):

    converted = pd.to_numeric(
        series,
        errors="coerce"
    )

    valid_ratio = converted.notna().mean()

    return converted if valid_ratio >= 0.80 else None


def try_date(series):

    converted = pd.to_datetime(
        series,
        errors="coerce"
    )

    valid_ratio = converted.notna().mean()

    return converted if valid_ratio >= 0.80 else None


# ============================================================
# COLUMN DETECTION
# ============================================================

def detect_columns(df):

    numeric_columns = []
    categorical_columns = []
    date_columns = []
    id_columns = []

    for column in df.columns:

        series = df[column]

        # --------------------------------------------
        # NUMERIC
        # --------------------------------------------

        numeric_series = try_numeric(series)

        if numeric_series is not None:

            numeric_columns.append(column)

            continue

        # --------------------------------------------
        # DATE
        # --------------------------------------------

        date_series = try_date(series)

        if date_series is not None:

            date_columns.append(column)

            continue

        # --------------------------------------------
        # ID
        # --------------------------------------------

        unique_ratio = (
            series.nunique(dropna=True)
            / max(len(series), 1)
        )

        column_lower = column.lower()

        if (
            "id" in column_lower
            or unique_ratio > 0.95
        ):

            id_columns.append(column)

        else:

            categorical_columns.append(column)

    return {

        "numeric": numeric_columns,

        "categorical": categorical_columns,

        "date": date_columns,

        "id": id_columns
    }


# ============================================================
# METRIC DETECTION
# ============================================================

def detect_business_metrics(df):
    """
    Detect which column represents each business metric.

    Uses substring matching (not just exact matches) so real-world
    column names like "TreatmentCost", "NetRevenue", or
    "UnitsShipped" are still recognized — not just the exact
    retail-style names ("Amount", "Profit", "Quantity"). A substring
    match is only accepted if the column is actually numeric, so a
    text column like "SalesPerson" doesn't get mistaken for the
    sales figure itself.
    """

    metrics = {}

    column_map = {
        column.lower().replace(" ", "").replace("_", ""):
            column
        for column in df.columns
    }

    def is_numeric_column(column_name):
        converted = pd.to_numeric(df[column_name], errors="coerce")
        return converted.notna().mean() >= 0.6

    def find_metric(exact_keys, substring_keys):

        # Exact match first — most reliable.
        for key in exact_keys:
            if key in column_map:
                return column_map[key]

        # Fall back to substring match, but only for numeric columns,
        # so we don't grab a text column like "SalesPerson".
        for normalized_name, original_name in column_map.items():
            for key in substring_keys:
                if key in normalized_name and is_numeric_column(original_name):
                    return original_name

        return None

    sales_column = find_metric(
        exact_keys=["amount", "sales", "revenue", "turnover", "totalamount"],
        substring_keys=["amount", "sales", "revenue", "turnover"]
    )
    if sales_column:
        metrics["sales"] = sales_column

    profit_column = find_metric(
        exact_keys=["profit", "netprofit", "grossprofit"],
        substring_keys=["profit", "margin"]
    )
    if profit_column:
        metrics["profit"] = profit_column

    quantity_column = find_metric(
        exact_keys=["quantity", "qty", "units", "volume"],
        substring_keys=["quantity", "qty", "units", "volume", "count"]
    )
    if quantity_column:
        metrics["quantity"] = quantity_column

    cost_column = find_metric(
        exact_keys=["cost", "totalcost", "expense", "expenses"],
        substring_keys=["cost", "expense", "fee"]
    )
    if cost_column:
        metrics["cost"] = cost_column

    return metrics


# ============================================================
# DYNAMIC KPI GENERATION
# ============================================================

def generate_kpis(df):

    df = clean_columns(df)

    detection = detect_columns(df)

    metrics = detect_business_metrics(df)

    kpis = {}

    # ========================================================
    # ROW COUNT
    # ========================================================

    kpis["total_rows"] = int(len(df))

    # ========================================================
    # UNIQUE COUNTS
    # ========================================================

    if detection["id"]:

        for column in detection["id"][:3]:

            kpis[
                f"unique_{column.lower()}"
            ] = int(
                df[column]
                .nunique(dropna=True)
            )

    # ========================================================
    # SALES
    # ========================================================

    if "sales" in metrics:

        sales = pd.to_numeric(
            df[metrics["sales"]],
            errors="coerce"
        ).fillna(0)

        kpis["total_sales"] = float(
            sales.sum()
        )

        kpis["average_sales"] = float(
            sales.mean()
        )

        kpis["maximum_sale"] = float(
            sales.max()
        )

        kpis["minimum_sale"] = float(
            sales.min()
        )

    # ========================================================
    # PROFIT
    # ========================================================

    if "profit" in metrics:

        profit = pd.to_numeric(
            df[metrics["profit"]],
            errors="coerce"
        ).fillna(0)

        kpis["total_profit"] = float(
            profit.sum()
        )

        kpis["average_profit"] = float(
            profit.mean()
        )

        if "sales" in metrics:

            sales = pd.to_numeric(
                df[metrics["sales"]],
                errors="coerce"
            ).fillna(0)

            total_sales = sales.sum()

            total_profit = profit.sum()

            if total_sales != 0:

                kpis["profit_margin"] = float(
                    total_profit
                    / total_sales
                    * 100
                )

    # ========================================================
    # QUANTITY
    # ========================================================

    if "quantity" in metrics:

        quantity = pd.to_numeric(
            df[metrics["quantity"]],
            errors="coerce"
        ).fillna(0)

        kpis["total_quantity"] = float(
            quantity.sum()
        )

        kpis["average_quantity"] = float(
            quantity.mean()
        )

    # ========================================================
    # COST
    # ========================================================

    if "cost" in metrics:

        cost = pd.to_numeric(
            df[metrics["cost"]],
            errors="coerce"
        ).fillna(0)

        kpis["total_cost"] = float(
            cost.sum()
        )

    # ========================================================
    # CATEGORICAL COUNTS
    # ========================================================

    kpis["category_counts"] = {}

    for column in detection["categorical"]:

        kpis["category_counts"][column] = int(
            df[column]
            .nunique(dropna=True)
        )

    # ========================================================
    # DATE RANGE
    # ========================================================

    if detection["date"]:

        date_column = detection["date"][0]

        dates = pd.to_datetime(
            df[date_column],
            errors="coerce"
        ).dropna()

        if not dates.empty:

            kpis["date_column"] = date_column

            kpis["start_date"] = str(
                dates.min().date()
            )

            kpis["end_date"] = str(
                dates.max().date()
            )

            kpis["days_covered"] = int(
                (
                    dates.max()
                    - dates.min()
                ).days + 1
            )

    return kpis


# ============================================================
# DATASET PROFILE
# ============================================================

def suggest_questions(df, detection, metrics):
    """
    Build a list of natural-language questions relevant to THIS
    dataset, based only on what was actually detected — works for
    any business domain, not just sales/retail.
    """

    questions = []

    if "sales" in metrics:
        questions.append("What are the total sales?")

    if "profit" in metrics:
        questions.append("What's the total profit and margin?")

    if "cost" in metrics:
        questions.append("What are the total costs?")

    if "quantity" in metrics:
        questions.append("What's the total quantity or volume?")

    # Pick up to two categorical columns for "best-performing X"
    # style questions, skipping obvious ID-like columns.
    categorical = [
        c for c in detection.get("categorical", [])
        if c.lower() not in ("id", "orderid", "order_id")
    ][:2]

    value_metric = "sales" if "sales" in metrics else (
        "profit" if "profit" in metrics else None
    )

    for column in categorical:
        if value_metric:
            questions.append(f"Which {column.lower()} performed best?")
        else:
            questions.append(f"Show me a breakdown by {column.lower()}.")

    if detection.get("date") and value_metric:
        questions.append("Show me the trend over time.")

    if value_metric:
        questions.append("Why did performance change recently?")

    questions.append("Give me a business summary.")
    questions.append("What are your recommendations?")

    # De-duplicate while preserving order, cap at 6 so the chip
    # row stays scannable.
    seen = set()
    unique_questions = []

    for q in questions:
        if q not in seen:
            seen.add(q)
            unique_questions.append(q)

    return unique_questions[:6]


def profile_dataset(df):

    df = clean_columns(df)

    detection = detect_columns(df)

    metrics = detect_business_metrics(df)

    kpis = generate_kpis(df)

    return {

        "dataset": {

            "rows": int(len(df)),

            "columns": int(len(df.columns)),

            "column_names":
                list(df.columns)
        },

        "detected_columns": detection,

        "business_metrics": metrics,

        "kpis": kpis,

        "suggested_questions": suggest_questions(df, detection, metrics)
    }


# ============================================================
# FILE ANALYSIS
# ============================================================

def analyze_dataset_file(file_path):

    df = pd.read_csv(file_path)

    return profile_dataset(df)


# ============================================================
# EXISTING APP COMPATIBILITY
# ============================================================

def dataset_intelligence(file_path):

    return analyze_dataset_file(
        file_path
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "\n===== PHASE 6.1 DATASET INTELLIGENCE =====\n"
    )

    try:

        result = analyze_dataset_file(
            "dmart_orders_2024.csv"
        )

        print("\nDATASET PROFILE")
        print(result["dataset"])

        print("\nDETECTED COLUMNS")
        print(result["detected_columns"])

        print("\nBUSINESS METRICS")
        print(result["business_metrics"])

        print("\nDYNAMIC KPIs")

        for key, value in result["kpis"].items():

            print(
                f"{key}: {value}"
            )

        print(
            "\n✅ PHASE 6.1 ENGINE TEST PASSED"
        )

    except Exception as error:

        print(
            "\n❌ PHASE 6.1 ERROR:",
            repr(error)
        )