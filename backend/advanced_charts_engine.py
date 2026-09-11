# ============================================================
# 📊 ADVANCED CHARTS ENGINE
# Phase 6.7 — Advanced Chart Intelligence
# ============================================================

import pandas as pd
import numpy as np


# ============================================================
# 1. COLUMN DETECTION
# ============================================================

def detect_numeric_columns(df):
    """
    Detect numeric columns from dataframe.
    """

    numeric_columns = []

    for column in df.columns:
        if pd.api.types.is_numeric_dtype(df[column]):
            numeric_columns.append(column)

    return numeric_columns


def detect_category_columns(df):
    """
    Detect suitable categorical columns.

    Suitable examples:
    Category
    City
    Product
    Region
    Department
    Customer
    State
    Payment
    Status
    """

    preferred_names = [
        "category",
        "city",
        "product",
        "region",
        "department",
        "customer",
        "state",
        "payment",
        "payment_method",
        "status",
        "food_category",
        "restaurant"
    ]

    category_columns = []

    # First: preferred business columns
    for column in df.columns:

        column_lower = str(column).lower().strip()

        if column_lower in preferred_names:

            if not pd.api.types.is_numeric_dtype(df[column]):

                unique_count = df[column].nunique(dropna=True)

                if 1 < unique_count <= 100:
                    category_columns.append(column)

    # Second: automatically detect object/category columns
    for column in df.columns:

        if column in category_columns:
            continue

        if (
            pd.api.types.is_object_dtype(df[column])
            or isinstance(df[column].dtype, pd.CategoricalDtype)
        ):

            unique_count = df[column].nunique(dropna=True)

            if 1 < unique_count <= 100:
                category_columns.append(column)

    return category_columns


# ============================================================
# 2. DATE COLUMN DETECTION
# ============================================================

def detect_date_columns(df):

    date_columns = []

    for column in df.columns:

        column_lower = str(column).lower()

        if any(
            keyword in column_lower
            for keyword in [
                "date",
                "time",
                "month",
                "year"
            ]
        ):

            try:

                converted = pd.to_datetime(
                    df[column],
                    errors="coerce"
                )

                if converted.notna().sum() > 0:

                    date_columns.append(column)

            except Exception:
                pass

    return date_columns


# ============================================================
# 3. SELECT VALUE COLUMN
# ============================================================

def select_value_column(numeric_columns):

    preferred_values = [
        "sales",
        "revenue",
        "amount",
        "net_sales",
        "order_amount",
        "profit",
        "profit_amount",
        "total_sales"
    ]

    for preferred in preferred_values:

        for column in numeric_columns:

            if str(column).lower() == preferred:
                return column

    # fallback
    return numeric_columns[0]


# ============================================================
# 4. CATEGORY COMPARISON CHART
# ============================================================

def category_comparison_chart(df):

    if df is None or df.empty:

        return {
            "success": False,
            "error": "Dataset is empty."
        }

    numeric_columns = detect_numeric_columns(df)
    category_columns = detect_category_columns(df)

    # --------------------------------------------------------
    # Numeric validation
    # --------------------------------------------------------

    if not numeric_columns:

        return {
            "success": False,
            "error": "No numeric value column found."
        }

    # --------------------------------------------------------
    # Category validation
    # --------------------------------------------------------

    if not category_columns:

        return {
            "success": False,
            "error": (
                "No suitable category column found. "
                "Dataset needs a categorical column such as "
                "Category, City, Product, Region, or Department."
            )
        }

    # --------------------------------------------------------
    # Select columns
    # --------------------------------------------------------

    category_column = category_columns[0]

    value_column = select_value_column(
        numeric_columns
    )

    # --------------------------------------------------------
    # Clean data
    # --------------------------------------------------------

    working_df = df[
        [category_column, value_column]
    ].copy()

    working_df[value_column] = pd.to_numeric(
        working_df[value_column],
        errors="coerce"
    )

    working_df = working_df.dropna(
        subset=[
            category_column,
            value_column
        ]
    )

    if working_df.empty:

        return {
            "success": False,
            "error": "No valid category/value data available."
        }

    # --------------------------------------------------------
    # Group by category
    # --------------------------------------------------------

    grouped = (
        working_df
        .groupby(category_column)[value_column]
        .sum()
        .sort_values(
            ascending=False
        )
    )

    # --------------------------------------------------------
    # Limit chart to top 10
    # --------------------------------------------------------

    grouped = grouped.head(10)

    labels = [
        str(value)
        for value in grouped.index
    ]

    values = [
        round(float(value), 2)
        for value in grouped.values
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_value = float(
        grouped.sum()
    )

    average_value = float(
        grouped.mean()
    )

    top_category = (
        labels[0]
        if labels
        else None
    )

    top_value = (
        values[0]
        if values
        else 0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "success": True,

        "chart": {
            "type": "bar",
            "title": (
                f"{value_column} by "
                f"{category_column}"
            ),
            "category_column": category_column,
            "value_column": value_column
        },

        "data": {

            "labels": labels,

            "values": values
        },

        "summary": {

            "total_value": round(
                total_value,
                2
            ),

            "average_value": round(
                average_value,
                2
            ),

            "category_count": len(
                labels
            ),

            "top_category": top_category,

            "top_category_value": round(
                top_value,
                2
            )
        }
    }

# ============================================================
# 5. CITY COMPARISON CHART
# ============================================================

def city_comparison_chart(df):

    if df is None or df.empty:

        return {
            "success": False,
            "error": "Dataset is empty."
        }

    numeric_columns = detect_numeric_columns(df)

    if not numeric_columns:

        return {
            "success": False,
            "error": "No numeric value column found."
        }

    # --------------------------------------------------------
    # Find City column
    # --------------------------------------------------------

    city_column = None

    for column in df.columns:

        column_lower = str(column).strip().lower()

        if column_lower == "city":
            city_column = column
            break

    # --------------------------------------------------------
    # Fallback: detect location-like column
    # --------------------------------------------------------

    if city_column is None:

        for column in df.columns:

            column_lower = str(column).strip().lower()

            if (
                "city" in column_lower
                or "location" in column_lower
            ):
                city_column = column
                break

    if city_column is None:

        return {
            "success": False,
            "error": (
                "No City column found. "
                "Dataset needs a City or Location column."
            )
        }

    # --------------------------------------------------------
    # Select value column
    # --------------------------------------------------------

    value_column = select_value_column(
        numeric_columns
    )

    # --------------------------------------------------------
    # Clean data
    # --------------------------------------------------------

    working_df = df[
        [city_column, value_column]
    ].copy()

    working_df[value_column] = pd.to_numeric(
        working_df[value_column],
        errors="coerce"
    )

    working_df = working_df.dropna(
        subset=[
            city_column,
            value_column
        ]
    )

    if working_df.empty:

        return {
            "success": False,
            "error": "No valid city/value data available."
        }

    # --------------------------------------------------------
    # Group by City
    # --------------------------------------------------------

    grouped = (
        working_df
        .groupby(city_column)[value_column]
        .sum()
        .sort_values(
            ascending=False
        )
    )

    # Top 10 cities
    grouped = grouped.head(10)

    labels = [
        str(value)
        for value in grouped.index
    ]

    values = [
        round(float(value), 2)
        for value in grouped.values
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_value = float(
        grouped.sum()
    )

    average_value = float(
        grouped.mean()
    )

    top_city = (
        labels[0]
        if labels
        else None
    )

    top_city_value = (
        values[0]
        if values
        else 0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "success": True,

        "chart": {
            "type": "bar",
            "title": (
                f"{value_column} by City"
            ),
            "category_column": city_column,
            "value_column": value_column
        },

        "data": {

            "labels": labels,

            "values": values
        },

        "summary": {

            "total_value": round(
                total_value,
                2
            ),

            "average_value": round(
                average_value,
                2
            ),

            "city_count": len(
                labels
            ),

            "top_city": top_city,

            "top_city_value": round(
                top_city_value,
                2
            )
        }
    }
# ============================================================
# 6. PAYMENT METHOD COMPARISON CHART
# ============================================================

def payment_method_comparison_chart(df):

    if df is None or df.empty:

        return {
            "success": False,
            "error": "Dataset is empty."
        }

    numeric_columns = detect_numeric_columns(df)

    if not numeric_columns:

        return {
            "success": False,
            "error": "No numeric value column found."
        }

    # --------------------------------------------------------
    # Find Payment Method column
    # --------------------------------------------------------

    payment_column = None

    for column in df.columns:

        column_lower = str(column).strip().lower()

        if (
            column_lower == "payment_method"
            or column_lower == "payment method"
            or column_lower == "payment"
        ):
            payment_column = column
            break

    # --------------------------------------------------------
    # Fallback detection
    # --------------------------------------------------------

    if payment_column is None:

        for column in df.columns:

            column_lower = str(column).strip().lower()

            if "payment" in column_lower:

                payment_column = column
                break

    if payment_column is None:

        return {
            "success": False,
            "error": (
                "No Payment Method column found. "
                "Dataset needs a Payment Method or Payment column."
            )
        }

    # --------------------------------------------------------
    # Select value column
    # --------------------------------------------------------

    value_column = select_value_column(
        numeric_columns
    )

    # --------------------------------------------------------
    # Clean data
    # --------------------------------------------------------

    working_df = df[
        [payment_column, value_column]
    ].copy()

    working_df[value_column] = pd.to_numeric(
        working_df[value_column],
        errors="coerce"
    )

    working_df = working_df.dropna(
        subset=[
            payment_column,
            value_column
        ]
    )

    if working_df.empty:

        return {
            "success": False,
            "error": (
                "No valid payment/value data available."
            )
        }

    # --------------------------------------------------------
    # Group by Payment Method
    # --------------------------------------------------------

    grouped = (
        working_df
        .groupby(payment_column)[value_column]
        .sum()
        .sort_values(
            ascending=False
        )
    )

    # Top 10
    grouped = grouped.head(10)

    labels = [
        str(value)
        for value in grouped.index
    ]

    values = [
        round(float(value), 2)
        for value in grouped.values
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_value = float(
        grouped.sum()
    )

    average_value = float(
        grouped.mean()
    )

    top_payment = (
        labels[0]
        if labels
        else None
    )

    top_payment_value = (
        values[0]
        if values
        else 0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "success": True,

        "chart": {

            "type": "bar",

            "title": (
                f"{value_column} by "
                f"Payment Method"
            ),

            "category_column": payment_column,

            "value_column": value_column
        },

        "data": {

            "labels": labels,

            "values": values
        },

        "summary": {

            "total_value": round(
                total_value,
                2
            ),

            "average_value": round(
                average_value,
                2
            ),

            "payment_method_count": len(
                labels
            ),

            "top_payment_method": top_payment,

            "top_payment_method_value": round(
                top_payment_value,
                2
            )
        }
    }
# ============================================================
# 7. PRODUCT COMPARISON CHART
# ============================================================

def product_comparison_chart(df):

    if df is None or df.empty:
        return {
            "success": False,
            "error": "Dataset is empty."
        }

    numeric_columns = detect_numeric_columns(df)

    if not numeric_columns:
        return {
            "success": False,
            "error": "No numeric value column found."
        }

    # --------------------------------------------------------
    # Find Product column
    # --------------------------------------------------------

    product_column = None

    for column in df.columns:

        column_lower = str(column).strip().lower()

        if column_lower == "product":
            product_column = column
            break

    # --------------------------------------------------------
    # Fallback detection
    # --------------------------------------------------------

    if product_column is None:

        for column in df.columns:

            column_lower = str(column).strip().lower()

            if "product" in column_lower:

                product_column = column
                break

    if product_column is None:
        return {
            "success": False,
            "error": (
                "No Product column found. "
                "Dataset needs a Product column."
            )
        }

    # --------------------------------------------------------
    # Select value column
    # --------------------------------------------------------

    value_column = select_value_column(
        numeric_columns
    )

    # --------------------------------------------------------
    # Clean data
    # --------------------------------------------------------

    working_df = df[
        [product_column, value_column]
    ].copy()

    working_df[value_column] = pd.to_numeric(
        working_df[value_column],
        errors="coerce"
    )

    working_df = working_df.dropna(
        subset=[
            product_column,
            value_column
        ]
    )

    if working_df.empty:
        return {
            "success": False,
            "error": (
                "No valid product/value data available."
            )
        }

    # --------------------------------------------------------
    # Group by Product
    # --------------------------------------------------------

    grouped = (
        working_df
        .groupby(product_column)[value_column]
        .sum()
        .sort_values(
            ascending=False
        )
    )

    # Top 10 products
    grouped = grouped.head(10)

    labels = [
        str(value)
        for value in grouped.index
    ]

    values = [
        round(float(value), 2)
        for value in grouped.values
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_value = float(
        grouped.sum()
    )

    average_value = float(
        grouped.mean()
    )

    top_product = (
        labels[0]
        if labels
        else None
    )

    top_product_value = (
        values[0]
        if values
        else 0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "success": True,

        "chart": {

            "type": "bar",

            "title": (
                f"{value_column} by Product"
            ),

            "category_column": product_column,

            "value_column": value_column
        },

        "data": {

            "labels": labels,

            "values": values
        },

        "summary": {

            "total_value": round(
                total_value,
                2
            ),

            "average_value": round(
                average_value,
                2
            ),

            "product_count": len(
                labels
            ),

            "top_product": top_product,

            "top_product_value": round(
                top_product_value,
                2
            )
        }
    }
# ============================================================
# 8. ORDER STATUS COMPARISON CHART
# ============================================================

def order_status_comparison_chart(df):

    if df is None or df.empty:
        return {
            "success": False,
            "error": "Dataset is empty."
        }

    # --------------------------------------------------------
    # Detect numeric columns
    # --------------------------------------------------------

    numeric_columns = detect_numeric_columns(df)

    if not numeric_columns:
        return {
            "success": False,
            "error": "No numeric value column found."
        }

    # --------------------------------------------------------
    # Detect Order Status column
    # --------------------------------------------------------

    status_column = None

    # Exact / common names
    preferred_names = [
        "Order_Status",
        "Order Status",
        "OrderStatus",
        "order_status",
        "order status",
        "status",
        "Status"
    ]

    for preferred in preferred_names:

        for column in df.columns:

            if str(column).strip().lower() == preferred.lower():
                status_column = column
                break

        if status_column is not None:
            break

    # --------------------------------------------------------
    # Flexible detection
    # --------------------------------------------------------

    if status_column is None:

        for column in df.columns:

            column_lower = (
                str(column)
                .strip()
                .lower()
                .replace("_", " ")
                .replace("-", " ")
            )

            if (
                "order" in column_lower
                and "status" in column_lower
            ):
                status_column = column
                break

    # --------------------------------------------------------
    # Final status fallback
    # --------------------------------------------------------

    if status_column is None:

        for column in df.columns:

            column_lower = (
                str(column)
                .strip()
                .lower()
                .replace("_", " ")
                .replace("-", " ")
            )

            if "status" in column_lower:

                # Make sure it is not numeric
                if column not in numeric_columns:
                    status_column = column
                    break

    # --------------------------------------------------------
    # No status column
    # --------------------------------------------------------

    if status_column is None:

        return {
            "success": False,
            "error": (
                "No status column found. "
                "Expected a column such as "
                "Order_Status, Order Status, or Status."
            )
        }

    # --------------------------------------------------------
    # Select value column
    # --------------------------------------------------------

    value_column = select_value_column(
        numeric_columns
    )

    # --------------------------------------------------------
    # Prepare working data
    # --------------------------------------------------------

    working_df = df[
        [status_column, value_column]
    ].copy()

    # Numeric conversion
    working_df[value_column] = pd.to_numeric(
        working_df[value_column],
        errors="coerce"
    )

    # Clean status values
    working_df[status_column] = (
        working_df[status_column]
        .astype(str)
        .str.strip()
    )

    working_df = working_df[
        (working_df[status_column] != "")
        & (working_df[status_column].str.lower() != "nan")
    ]

    working_df = working_df.dropna(
        subset=[value_column]
    )

    if working_df.empty:

        return {
            "success": False,
            "error": (
                "No valid order status/value data available."
            )
        }

    # --------------------------------------------------------
    # Group by status
    # --------------------------------------------------------

    grouped = (
        working_df
        .groupby(status_column)[value_column]
        .sum()
        .sort_values(
            ascending=False
        )
    )

    # Limit to top 10
    grouped = grouped.head(10)

    # --------------------------------------------------------
    # Chart data
    # --------------------------------------------------------

    labels = [
        str(value)
        for value in grouped.index
    ]

    values = [
        round(float(value), 2)
        for value in grouped.values
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_value = float(
        grouped.sum()
    )

    average_value = (
        float(grouped.mean())
        if len(grouped) > 0
        else 0
    )

    top_status = (
        labels[0]
        if labels
        else None
    )

    top_status_value = (
        values[0]
        if values
        else 0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "success": True,

        "chart": {

            "type": "bar",

            "title": (
                f"{value_column} by "
                f"{status_column}"
            ),

            "category_column": status_column,

            "value_column": value_column
        },

        "data": {

            "labels": labels,

            "values": values
        },

        "summary": {

            "total_value": round(
                total_value,
                2
            ),

            "average_value": round(
                average_value,
                2
            ),

            "status_count": len(
                labels
            ),

            "top_status": top_status,

            "top_status_value": round(
                top_status_value,
                2
            )
        }
    }
# ============================================================
# 9. MONTHLY SALES COMPARISON CHART — 6.7.7
# ============================================================

def monthly_sales_comparison_chart(df):

    if df is None or df.empty:
        return {
            "success": False,
            "error": "Dataset is empty."
        }

    # --------------------------------------------------------
    # Detect columns
    # --------------------------------------------------------

    numeric_columns = detect_numeric_columns(df)
    date_columns = detect_date_columns(df)

    if not numeric_columns:
        return {
            "success": False,
            "error": "No numeric value column found."
        }

    if not date_columns:
        return {
            "success": False,
            "error": (
                "No date column found. "
                "Dataset needs a date column such as "
                "Order_Date or Date."
            )
        }

    # --------------------------------------------------------
    # Select columns
    # --------------------------------------------------------

    date_column = date_columns[0]

    value_column = select_value_column(
        numeric_columns
    )

    # --------------------------------------------------------
    # Prepare data
    # --------------------------------------------------------

    working_df = df[
        [date_column, value_column]
    ].copy()

    working_df[date_column] = pd.to_datetime(
        working_df[date_column],
        errors="coerce"
    )

    working_df[value_column] = pd.to_numeric(
        working_df[value_column],
        errors="coerce"
    )

    working_df = working_df.dropna(
        subset=[
            date_column,
            value_column
        ]
    )

    if working_df.empty:
        return {
            "success": False,
            "error": "No valid date/value data available."
        }

    # --------------------------------------------------------
    # Group by month
    # --------------------------------------------------------

    working_df["__month"] = (
        working_df[date_column]
        .dt.to_period("M")
    )

    grouped = (
        working_df
        .groupby("__month")[value_column]
        .sum()
        .sort_index()
    )

    # --------------------------------------------------------
    # Labels
    # --------------------------------------------------------

    labels = [
        period.strftime("%b %Y")
        for period in grouped.index
    ]

    values = [
        round(float(value), 2)
        for value in grouped.values
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_value = float(
        grouped.sum()
    )

    average_value = (
        float(grouped.mean())
        if len(grouped) > 0
        else 0
    )

    best_month = (
        labels[
            int(grouped.values.argmax())
        ]
        if len(grouped) > 0
        else None
    )

    best_month_value = (
        float(grouped.max())
        if len(grouped) > 0
        else 0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "success": True,

        "chart": {

            "type": "bar",

            "title": (
                f"{value_column} by Month"
            ),

            "date_column": date_column,

            "value_column": value_column
        },

        "data": {

            "labels": labels,

            "values": values
        },

        "summary": {

            "total_value": round(
                total_value,
                2
            ),

            "average_value": round(
                average_value,
                2
            ),

            "month_count": len(
                labels
            ),

            "best_month": best_month,

            "best_month_value": round(
                best_month_value,
                2
            )
        }
    }
# ============================================================
# 10. GROWTH ANALYSIS CHART — 6.7.8
# ============================================================

def growth_analysis_chart(df):

    if df is None or df.empty:
        return {
            "success": False,
            "error": "Dataset is empty."
        }

    # --------------------------------------------------------
    # Detect columns
    # --------------------------------------------------------

    numeric_columns = detect_numeric_columns(df)
    date_columns = detect_date_columns(df)

    if not numeric_columns:
        return {
            "success": False,
            "error": "No numeric value column found."
        }

    if not date_columns:
        return {
            "success": False,
            "error": (
                "No date column found. "
                "Dataset needs a date column such as "
                "Order_Date or Date."
            )
        }

    date_column = date_columns[0]

    value_column = select_value_column(
        numeric_columns
    )

    # --------------------------------------------------------
    # Prepare data
    # --------------------------------------------------------

    working_df = df[
        [date_column, value_column]
    ].copy()

    working_df[date_column] = pd.to_datetime(
        working_df[date_column],
        errors="coerce"
    )

    working_df[value_column] = pd.to_numeric(
        working_df[value_column],
        errors="coerce"
    )

    working_df = working_df.dropna(
        subset=[
            date_column,
            value_column
        ]
    )

    if working_df.empty:
        return {
            "success": False,
            "error": "No valid date/value data available."
        }

    # --------------------------------------------------------
    # Group by month
    # --------------------------------------------------------

    working_df["__month"] = (
        working_df[date_column]
        .dt.to_period("M")
    )

    grouped = (
        working_df
        .groupby("__month")[value_column]
        .sum()
        .sort_index()
    )

    if len(grouped) < 2:
        return {
            "success": False,
            "error": (
                "At least two months are required "
                "to calculate growth."
            )
        }

    # --------------------------------------------------------
    # Calculate growth %
    # --------------------------------------------------------

    growth_values = []

    for i in range(len(grouped)):

        current_value = float(
            grouped.iloc[i]
        )

        previous_value = float(
            grouped.iloc[i - 1]
        )

        if previous_value == 0:

            growth = 0

        else:

            growth = (
                (current_value - previous_value)
                / previous_value
            ) * 100

        growth_values.append(
            round(growth, 2)
        )

    # First month has no previous month
    growth_values[0] = 0

    # --------------------------------------------------------
    # Labels
    # --------------------------------------------------------

    labels = [
        period.strftime("%b %Y")
        for period in grouped.index
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    valid_growth = growth_values[1:]

    average_growth = (
        sum(valid_growth) / len(valid_growth)
        if valid_growth
        else 0
    )

    highest_growth_index = (
        growth_values.index(
            max(valid_growth)
        ) + 1
        if valid_growth
        else 0
    )

    lowest_growth_index = (
        growth_values.index(
            min(valid_growth)
        ) + 1
        if valid_growth
        else 0
    )

    highest_growth = (
        growth_values[highest_growth_index]
        if growth_values
        else 0
    )

    lowest_growth = (
        growth_values[lowest_growth_index]
        if growth_values
        else 0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "success": True,

        "chart": {

            "type": "line",

            "title": (
                f"{value_column} Growth Analysis"
            ),

            "date_column": date_column,

            "value_column": value_column,

            "metric": "growth_percentage"
        },

        "data": {

            "labels": labels,

            "values": growth_values
        },

        "summary": {

            "average_growth": round(
                average_growth,
                2
            ),

            "highest_growth": round(
                highest_growth,
                2
            ),

            "highest_growth_month": (
                labels[highest_growth_index]
                if labels
                else None
            ),

            "lowest_growth": round(
                lowest_growth,
                2
            ),

            "lowest_growth_month": (
                labels[lowest_growth_index]
                if labels
                else None
            ),

            "period_count": len(
                labels
            )
        }
    }
# ============================================================
# 11. PROFIT ANALYSIS CHART — 6.7.9
# ============================================================

def profit_analysis_chart(df):

    if df is None or df.empty:
        return {
            "success": False,
            "error": "Dataset is empty."
        }

    numeric_columns = detect_numeric_columns(df)
    date_columns = detect_date_columns(df)

    if not numeric_columns:
        return {
            "success": False,
            "error": "No numeric value column found."
        }

    if not date_columns:
        return {
            "success": False,
            "error": (
                "No date column found. "
                "Dataset needs a date column such as "
                "Order_Date or Date."
            )
        }

    # --------------------------------------------------------
    # Find Profit column
    # --------------------------------------------------------

    profit_column = None

    preferred_names = [
        "Profit",
        "profit",
        "Total_Profit",
        "Total Profit",
        "Net_Profit",
        "Net Profit"
    ]

    for preferred in preferred_names:
        for column in df.columns:
            if str(column).strip().lower() == preferred.lower():
                profit_column = column
                break

        if profit_column is not None:
            break

    # Flexible detection
    if profit_column is None:
        for column in numeric_columns:

            column_lower = (
                str(column)
                .strip()
                .lower()
                .replace("_", " ")
                .replace("-", " ")
            )

            if "profit" in column_lower:
                profit_column = column
                break

    if profit_column is None:
        return {
            "success": False,
            "error": (
                "No Profit column found. "
                "Dataset needs a Profit column."
            )
        }

    date_column = date_columns[0]

    # --------------------------------------------------------
    # Prepare data
    # --------------------------------------------------------

    working_df = df[
        [date_column, profit_column]
    ].copy()

    working_df[date_column] = pd.to_datetime(
        working_df[date_column],
        errors="coerce"
    )

    working_df[profit_column] = pd.to_numeric(
        working_df[profit_column],
        errors="coerce"
    )

    working_df = working_df.dropna(
        subset=[
            date_column,
            profit_column
        ]
    )

    if working_df.empty:
        return {
            "success": False,
            "error": "No valid date/profit data available."
        }

    # --------------------------------------------------------
    # Group by month
    # --------------------------------------------------------

    working_df["__month"] = (
        working_df[date_column]
        .dt.to_period("M")
    )

    grouped = (
        working_df
        .groupby("__month")[profit_column]
        .sum()
        .sort_index()
    )

    # --------------------------------------------------------
    # Chart data
    # --------------------------------------------------------

    labels = [
        period.strftime("%b %Y")
        for period in grouped.index
    ]

    values = [
        round(float(value), 2)
        for value in grouped.values
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_profit = float(
        grouped.sum()
    )

    average_profit = (
        float(grouped.mean())
        if len(grouped) > 0
        else 0
    )

    best_index = (
        int(grouped.values.argmax())
        if len(grouped) > 0
        else 0
    )

    worst_index = (
        int(grouped.values.argmin())
        if len(grouped) > 0
        else 0
    )

    best_month = (
        labels[best_index]
        if labels
        else None
    )

    worst_month = (
        labels[worst_index]
        if labels
        else None
    )

    best_profit = (
        values[best_index]
        if values
        else 0
    )

    worst_profit = (
        values[worst_index]
        if values
        else 0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "success": True,

        "chart": {

            "type": "line",

            "title": "Profit Analysis by Month",

            "date_column": date_column,

            "value_column": profit_column,

            "metric": "profit"
        },

        "data": {

            "labels": labels,

            "values": values
        },

        "summary": {

            "total_profit": round(
                total_profit,
                2
            ),

            "average_profit": round(
                average_profit,
                2
            ),

            "best_month": best_month,

            "best_month_profit": round(
                best_profit,
                2
            ),

            "worst_month": worst_month,

            "worst_month_profit": round(
                worst_profit,
                2
            ),

            "month_count": len(
                labels
            )
        }
    }  
# ============================================================
# 12. CUSTOMER ANALYSIS CHART — 6.7.10
# ============================================================

def customer_analysis_chart(df):

    if df is None or df.empty:
        return {
            "success": False,
            "error": "Dataset is empty."
        }

    numeric_columns = detect_numeric_columns(df)

    if not numeric_columns:
        return {
            "success": False,
            "error": "No numeric value column found."
        }

    # --------------------------------------------------------
    # Find Customer column
    # --------------------------------------------------------

    customer_column = None

    preferred_names = [
        "Customer_ID",
        "Customer ID",
        "Customer",
        "CustomerID",
        "customer_id",
        "customer"
    ]

    for preferred in preferred_names:

        for column in df.columns:

            if str(column).strip().lower() == preferred.lower():
                customer_column = column
                break

        if customer_column is not None:
            break

    # Flexible detection
    if customer_column is None:

        for column in df.columns:

            column_lower = (
                str(column)
                .strip()
                .lower()
                .replace("_", " ")
                .replace("-", " ")
            )

            if "customer" in column_lower:

                if column not in numeric_columns:
                    customer_column = column
                    break

    if customer_column is None:
        return {
            "success": False,
            "error": (
                "No Customer column found. "
                "Dataset needs a Customer or Customer_ID column."
            )
        }

    # --------------------------------------------------------
    # Select sales/value column
    # --------------------------------------------------------

    value_column = select_value_column(
        numeric_columns
    )

    # --------------------------------------------------------
    # Prepare data
    # --------------------------------------------------------

    working_df = df[
        [customer_column, value_column]
    ].copy()

    working_df[value_column] = pd.to_numeric(
        working_df[value_column],
        errors="coerce"
    )

    working_df[customer_column] = (
        working_df[customer_column]
        .astype(str)
        .str.strip()
    )

    working_df = working_df[
        (working_df[customer_column] != "")
        & (working_df[customer_column].str.lower() != "nan")
    ]

    working_df = working_df.dropna(
        subset=[value_column]
    )

    if working_df.empty:
        return {
            "success": False,
            "error": "No valid customer/value data available."
        }

    # --------------------------------------------------------
    # Customer sales
    # --------------------------------------------------------

    grouped = (
        working_df
        .groupby(customer_column)[value_column]
        .sum()
        .sort_values(
            ascending=False
        )
        .head(10)
    )

    labels = [
        str(value)
        for value in grouped.index
    ]

    values = [
        round(float(value), 2)
        for value in grouped.values
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_customer_sales = float(
        grouped.sum()
    )

    average_customer_sales = (
        float(grouped.mean())
        if len(grouped) > 0
        else 0
    )

    top_customer = (
        labels[0]
        if labels
        else None
    )

    top_customer_value = (
        values[0]
        if values
        else 0
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {

        "success": True,

        "chart": {

            "type": "bar",

            "title": (
                f"Top Customers by "
                f"{value_column}"
            ),

            "category_column": customer_column,

            "value_column": value_column,

            "metric": "customer_sales"
        },

        "data": {

            "labels": labels,

            "values": values
        },

        "summary": {

            "total_customer_sales": round(
                total_customer_sales,
                2
            ),

            "average_customer_sales": round(
                average_customer_sales,
                2
            ),

            "customer_count": len(
                labels
            ),

            "top_customer": top_customer,

            "top_customer_value": round(
                top_customer_value,
                2
            )
        }
    }              
# ============================================================
# 5. GENERAL CHART DATA GENERATOR
# ============================================================

def generate_chart_data(df):

    if df is None or df.empty:

        return {
            "success": False,
            "error": "Dataset is empty."
        }

    numeric_columns = detect_numeric_columns(df)

    date_columns = detect_date_columns(df)

    category_columns = detect_category_columns(df)

    # --------------------------------------------------------
    # Numeric validation
    # --------------------------------------------------------

    if not numeric_columns:

        return {
            "success": False,
            "error": "No numeric value column found."
        }

    value_column = select_value_column(
        numeric_columns
    )

    # ========================================================
    # DATE BASED LINE CHART
    # ========================================================

    if date_columns:

        date_column = date_columns[0]

        working_df = df[
            [date_column, value_column]
        ].copy()

        working_df[date_column] = pd.to_datetime(
            working_df[date_column],
            errors="coerce"
        )

        working_df[value_column] = pd.to_numeric(
            working_df[value_column],
            errors="coerce"
        )

        working_df = working_df.dropna()

        if not working_df.empty:

            grouped = (
                working_df
                .groupby(date_column)[value_column]
                .sum()
                .sort_index()
                .head(100)
            )

            labels = [
                date.strftime("%Y-%m-%d")
                for date in grouped.index
            ]

            values = [
                round(float(value), 2)
                for value in grouped.values
            ]

            return {

                "success": True,

                "chart": {
                    "type": "line",
                    "title": (
                        f"{value_column} / "
                        f"Revenue Analysis"
                    ),
                    "date_column": date_column,
                    "value_column": value_column
                },

                "data": {
                    "labels": labels,
                    "values": values
                },

                "summary": {

                    "total_sales": round(
                        float(grouped.sum()),
                        2
                    ),

                    "average_sales": round(
                        float(grouped.mean()),
                        2
                    ),

                    "data_points": len(
                        grouped
                    )
                }
            }

    # ========================================================
    # CATEGORY BASED BAR CHART
    # ========================================================

    if category_columns:

        return category_comparison_chart(df)

    # ========================================================
    # NO CHART POSSIBLE
    # ========================================================

    return {

        "success": False,

        "error": (
            "Could not determine a suitable "
            "chart structure."
        )
    }


# ============================================================
# 6. TEST DATA
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # Test 1 — Category Comparison
    # --------------------------------------------------------

    test_data = pd.DataFrame({

        "Order_Date": [
            "2026-01-01",
            "2026-01-02",
            "2026-01-03",
            "2026-01-04",
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
            "2026-01-08",
            "2026-01-09",
            "2026-01-10"
        ],

        "Category": [
            "Electronics",
            "Clothing",
            "Electronics",
            "Food",
            "Clothing",
            "Food",
            "Electronics",
            "Food",
            "Clothing",
            "Electronics"
        ],

        "Sales": [
            1000,
            1200,
            1500,
            800,
            1400,
            1100,
            1800,
            1300,
            1600,
            1900
        ],

        "Profit": [
            200,
            240,
            300,
            160,
            280,
            220,
            360,
            260,
            320,
            380
        ],

        "Quantity": [
            2,
            4,
            3,
            5,
            4,
            6,
            3,
            5,
            4,
            2
        ]
    })

    # --------------------------------------------------------
    # Run Category Comparison
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("📊 CATEGORY COMPARISON CHART")
    print("=" * 60)

    result = category_comparison_chart(
        test_data
    )

    print(result)

    # --------------------------------------------------------
    # Run General Chart Generator
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("📈 GENERAL CHART DATA")
    print("=" * 60)

    chart_result = generate_chart_data(
        test_data
    )

    print(chart_result)