"""
PHASE 6.2 — Dynamic KPI / Analytics Engine

Generates useful KPIs from any pandas DataFrame without requiring
a fixed dataset schema.

The engine:
- Detects numeric, categorical, and date columns
- Calculates dataset-wide KPIs
- Detects common business metrics such as sales/revenue, profit,
  quantity, orders, customers, and products when those columns exist
- Calculates averages and unique counts
- Returns a clean JSON-friendly dictionary for Flask/frontend use
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import re

import pandas as pd


# -------------------------------------------------------------------
# COLUMN NAME HELPERS
# -------------------------------------------------------------------

def _clean_name(name: Any) -> str:
    """Convert a column name into a simple searchable form."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _column_map(df: pd.DataFrame) -> Dict[str, str]:
    """
    Map normalized column names -> original column names.
    Example: 'Order Amount' -> {'order_amount': 'Order Amount'}
    """
    return {_clean_name(col): col for col in df.columns}


def _find_column(
    df: pd.DataFrame,
    aliases: List[str]
) -> Optional[str]:
    """
    Find the first existing column whose normalized name matches
    an alias or contains an alias.
    """
    mapping = _column_map(df)

    # Exact match first
    for alias in aliases:
        alias_clean = _clean_name(alias)
        if alias_clean in mapping:
            return mapping[alias_clean]

    # Partial match second
    for alias in aliases:
        alias_clean = _clean_name(alias)
        for normalized, original in mapping.items():
            if (
                alias_clean in normalized
                or normalized in alias_clean
            ):
                return original

    return None


def _numeric_columns(df: pd.DataFrame) -> List[str]:
    """Return columns that contain numeric data."""
    result = []

    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() > 0:
            result.append(col)

    return result


def _date_columns(df: pd.DataFrame) -> List[str]:
    """Detect columns that can reasonably be interpreted as dates."""
    result = []

    for col in df.columns:
        name = _clean_name(col)

        # Strong date-name signal
        if any(token in name for token in
               ["date", "time", "month", "year", "day"]):
            parsed = pd.to_datetime(
                df[col],
                errors="coerce"
            )
            if parsed.notna().sum() > 0:
                result.append(col)
                continue

        # Conservative fallback: only accept if most values parse
        # successfully and the column is not obviously numeric.
        if not pd.api.types.is_numeric_dtype(df[col]):
            parsed = pd.to_datetime(
                df[col],
                errors="coerce"
            )
            if len(df) > 0 and parsed.notna().mean() >= 0.80:
                result.append(col)

    return result


def _safe_number(value: Any) -> float:
    """Convert pandas/numpy numeric values to normal Python float."""
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


# -------------------------------------------------------------------
# MAIN KPI ENGINE
# -------------------------------------------------------------------

def calculate_dynamic_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate dynamic KPIs from the supplied DataFrame.

    Returns a JSON-friendly dictionary:
    {
        "kpis": {...},
        "metric_columns": [...],
        "dimension_columns": [...],
        "date_columns": [...],
        "detected_metrics": {...}
    }
    """

    if df is None:
        return {
            "kpis": {},
            "metric_columns": [],
            "dimension_columns": [],
            "date_columns": [],
            "detected_metrics": {},
            "error": "No dataset supplied."
        }

    if not isinstance(df, pd.DataFrame):
        return {
            "kpis": {},
            "metric_columns": [],
            "dimension_columns": [],
            "date_columns": [],
            "detected_metrics": {},
            "error": "Input must be a pandas DataFrame."
        }

    if df.empty:
        return {
            "kpis": {
                "total_rows": 0,
                "total_columns": int(len(df.columns))
            },
            "metric_columns": [],
            "dimension_columns": list(map(str, df.columns)),
            "date_columns": [],
            "detected_metrics": {},
            "error": "Dataset is empty."
        }

    data = df.copy()
    data.columns = [str(col).strip() for col in data.columns]

    numeric_cols = _numeric_columns(data)
    date_cols = _date_columns(data)

    dimension_cols = [
        col for col in data.columns
        if col not in numeric_cols and col not in date_cols
    ]

    # ---------------------------------------------------------------
    # Detect common business columns
    # ---------------------------------------------------------------

    sales_col = _find_column(
        data,
        [
            "sales",
            "sale",
            "revenue",
            "amount",
            "order_amount",
            "net_sales",
            "total_sales",
            "turnover"
        ]
    )

    profit_col = _find_column(
        data,
        [
            "profit",
            "net_profit",
            "gross_profit",
            "operating_profit"
        ]
    )

    quantity_col = _find_column(
        data,
        [
            "quantity",
            "qty",
            "units",
            "units_sold"
        ]
    )

    customer_col = _find_column(
        data,
        [
            "customer",
            "customer_id",
            "client",
            "client_id",
            "buyer",
            "buyer_id"
        ]
    )

    product_col = _find_column(
        data,
        [
            "product",
            "product_id",
            "item",
            "item_id",
            "sku",
            "sku_id"
        ]
    )

    order_col = _find_column(
        data,
        [
            "order_id",
            "order",
            "invoice",
            "invoice_id",
            "transaction_id",
            "transaction"
        ]
    )

    cost_col = _find_column(
        data,
        [
            "cost",
            "total_cost",
            "expense",
            "expenses",
            "fee"
        ]
    )

    # ---------------------------------------------------------------
    # Core KPIs
    # ---------------------------------------------------------------

    kpis: Dict[str, Any] = {
        "total_rows": int(len(data)),
        "total_columns": int(len(data.columns))
    }

    # ---------------------------------------------------------------
    # Sales / Revenue
    # ---------------------------------------------------------------

    if sales_col:
        sales = pd.to_numeric(
            data[sales_col],
            errors="coerce"
        ).fillna(0)

        total_sales = _safe_number(sales.sum())

        kpis["total_sales"] = total_sales
        kpis["average_sales"] = _safe_number(sales.mean())
        kpis["minimum_sales"] = _safe_number(sales.min())
        kpis["maximum_sales"] = _safe_number(sales.max())

    # ---------------------------------------------------------------
    # Profit
    # ---------------------------------------------------------------

    if profit_col:
        profit = pd.to_numeric(
            data[profit_col],
            errors="coerce"
        ).fillna(0)

        total_profit = _safe_number(profit.sum())

        kpis["total_profit"] = total_profit
        kpis["average_profit"] = _safe_number(profit.mean())

        if "total_sales" in kpis and kpis["total_sales"] != 0:
            kpis["profit_margin"] = (
                total_profit / kpis["total_sales"]
            ) * 100

    # ---------------------------------------------------------------
    # Quantity
    # ---------------------------------------------------------------

    if quantity_col:
        quantity = pd.to_numeric(
            data[quantity_col],
            errors="coerce"
        ).fillna(0)

        kpis["total_quantity"] = _safe_number(quantity.sum())
        kpis["average_quantity"] = _safe_number(quantity.mean())

    # ---------------------------------------------------------------
    # Cost
    # ---------------------------------------------------------------

    if cost_col:
        cost = pd.to_numeric(
            data[cost_col],
            errors="coerce"
        ).fillna(0)

        kpis["total_cost"] = _safe_number(cost.sum())
        kpis["average_cost"] = _safe_number(cost.mean())

    # ---------------------------------------------------------------
    # Orders
    # ---------------------------------------------------------------

    if order_col:
        kpis["unique_orders"] = int(
            data[order_col].nunique(dropna=True)
        )
    else:
        # Fallback: each row is treated as a transaction/order.
        kpis["total_orders"] = int(len(data))

    # ---------------------------------------------------------------
    # Customers
    # ---------------------------------------------------------------

    if customer_col:
        kpis["unique_customers"] = int(
            data[customer_col].nunique(dropna=True)
        )

    # ---------------------------------------------------------------
    # Products
    # ---------------------------------------------------------------

    if product_col:
        kpis["unique_products"] = int(
            data[product_col].nunique(dropna=True)
        )

    # ---------------------------------------------------------------
    # Average Order Value
    # ---------------------------------------------------------------

    if "total_sales" in kpis:
        denominator = kpis.get(
            "unique_orders",
            kpis.get("total_orders", len(data))
        )

        if denominator:
            kpis["average_order_value"] = (
                kpis["total_sales"] / denominator
            )

    # ---------------------------------------------------------------
    # Date range
    # ---------------------------------------------------------------

    if date_cols:
        best_date_col = date_cols[0]

        parsed_dates = pd.to_datetime(
            data[best_date_col],
            errors="coerce"
        ).dropna()

        if not parsed_dates.empty:
            kpis["date_column"] = best_date_col
            kpis["start_date"] = parsed_dates.min().strftime("%Y-%m-%d")
            kpis["end_date"] = parsed_dates.max().strftime("%Y-%m-%d")
            kpis["date_days"] = int(
                (parsed_dates.max() - parsed_dates.min()).days
            )

    # ---------------------------------------------------------------
    # Generic numeric-column statistics
    # ---------------------------------------------------------------

    numeric_summary: Dict[str, Dict[str, float]] = {}

    for col in numeric_cols:
        values = pd.to_numeric(
            data[col],
            errors="coerce"
        ).dropna()

        if values.empty:
            continue

        numeric_summary[str(col)] = {
            "sum": _safe_number(values.sum()),
            "mean": _safe_number(values.mean()),
            "minimum": _safe_number(values.min()),
            "maximum": _safe_number(values.max())
        }

    # Keep generic statistics separate so future phases
    # (statistical analysis, trends, anomaly detection) can reuse them.
    kpis["numeric_summary"] = numeric_summary

    # ---------------------------------------------------------------
    # Detected metric map
    # ---------------------------------------------------------------

    detected_metrics = {
        "sales_column": sales_col,
        "profit_column": profit_col,
        "quantity_column": quantity_col,
        "customer_column": customer_col,
        "product_column": product_col,
        "order_column": order_col
    }

    return {
        "kpis": kpis,
        "metric_columns": [str(col) for col in numeric_cols],
        "dimension_columns": [str(col) for col in dimension_cols],
        "date_columns": [str(col) for col in date_cols],
        "detected_metrics": detected_metrics
    }


# -------------------------------------------------------------------
# SIMPLE KPI RESPONSE FORMATTER
# -------------------------------------------------------------------

def format_kpi_summary(result: Dict[str, Any]) -> str:
    """
    Create a professional, categorized KPI summary
    for the AI Assistant.
    """

    kpis = result.get("kpis", {})

    if not kpis:
        return "No KPI information is available."

    lines = []

    # ==========================================================
    # HEADER
    # ==========================================================

    lines.append("📊 Dynamic KPI Summary")
    lines.append("")

    # ==========================================================
    # 💰 FINANCIAL KPIs
    # ==========================================================

    financial = []

    if "total_sales" in kpis:
        financial.append(
            f"• Total Sales: ₹{kpis['total_sales']:,.2f}"
        )

    if "average_sales" in kpis:
        financial.append(
            f"• Average Sales: ₹{kpis['average_sales']:,.2f}"
        )

    if "total_profit" in kpis:
        financial.append(
            f"• Total Profit: ₹{kpis['total_profit']:,.2f}"
        )

    if "average_profit" in kpis:
        financial.append(
            f"• Average Profit: ₹{kpis['average_profit']:,.2f}"
        )

    if "profit_margin" in kpis:
        financial.append(
            f"• Profit Margin: {kpis['profit_margin']:,.2f}%"
        )

    if "total_cost" in kpis:
        financial.append(
            f"• Total Cost: ₹{kpis['total_cost']:,.2f}"
        )

    if "average_cost" in kpis:
        financial.append(
            f"• Average Cost: ₹{kpis['average_cost']:,.2f}"
        )

    if "average_order_value" in kpis:
        financial.append(
            f"• Average Order Value: "
            f"₹{kpis['average_order_value']:,.2f}"
        )

    if financial:
        lines.append("💰 Financial KPIs")
        lines.extend(financial)
        lines.append("")

    # ==========================================================
    # 📦 ORDER KPIs
    # ==========================================================

    orders = []

    if "total_orders" in kpis:
        orders.append(
            f"• Total Orders: {kpis['total_orders']:,}"
        )

    if "unique_orders" in kpis:
        orders.append(
            f"• Unique Orders: {kpis['unique_orders']:,}"
        )

    if "total_quantity" in kpis:
        orders.append(
            f"• Total Quantity: {kpis['total_quantity']:,.2f}"
        )

    if "average_quantity" in kpis:
        orders.append(
            f"• Average Quantity: {kpis['average_quantity']:,.2f}"
        )

    if orders:
        lines.append("📦 Order KPIs")
        lines.extend(orders)
        lines.append("")

    # ==========================================================
    # 👥 CUSTOMER KPIs
    # ==========================================================

    customers = []

    if "unique_customers" in kpis:
        customers.append(
            f"• Unique Customers: "
            f"{kpis['unique_customers']:,}"
        )

    if customers:
        lines.append("👥 Customer KPIs")
        lines.extend(customers)
        lines.append("")

    # ==========================================================
    # 🛍️ PRODUCT KPIs
    # ==========================================================

    products = []

    if "unique_products" in kpis:
        products.append(
            f"• Unique Products: "
            f"{kpis['unique_products']:,}"
        )

    if products:
        lines.append("🛍️ Product KPIs")
        lines.extend(products)
        lines.append("")

    # ==========================================================
    # 📅 TIME KPIs
    # ==========================================================

    time_info = []

    if "start_date" in kpis and "end_date" in kpis:
        time_info.append(
            f"• Date Range: "
            f"{kpis['start_date']} → {kpis['end_date']}"
        )

    if "date_days" in kpis:
        time_info.append(
            f"• Period Length: "
            f"{kpis['date_days']:,} days"
        )

    if time_info:
        lines.append("📅 Time Analysis")
        lines.extend(time_info)
        lines.append("")

    # ==========================================================
    # 📈 SALES RANGE
    # ==========================================================

    range_info = []

    if "minimum_sales" in kpis:
        range_info.append(
            f"• Minimum Sale: "
            f"₹{kpis['minimum_sales']:,.2f}"
        )

    if "maximum_sales" in kpis:
        range_info.append(
            f"• Maximum Sale: "
            f"₹{kpis['maximum_sales']:,.2f}"
        )

    if range_info:
        lines.append("📈 Sales Range")
        lines.extend(range_info)
        lines.append("")

    # Remove final empty line
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)
# -------------------------------------------------------------------
# PUBLIC ALIAS
# -------------------------------------------------------------------

def dynamic_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """Short public function name for Flask integration."""
    return calculate_dynamic_kpis(df)
