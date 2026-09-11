# ============================================================
# 🔥 PHASE 5.5 — ROOT CAUSE ENGINE
# ============================================================
#
# Purpose:
# Find WHY business performance changed between two files.
#
# Example:
# 2024 Sales > 2025 Sales
#
# Engine checks:
#   • Sales
#   • Profit
#   • Quantity
#   • Profit margin
#   • Product drivers
#   • City drivers
#   • Category drivers
#   • Monthly drivers
#   • New / removed items
#   • Volume vs price impact
#
# ============================================================

import os
import re
import pandas as pd


# ============================================================
# HELPERS
# ============================================================

def money(value):
    return f"₹{value:,.2f}"


def number(value):
    return f"{value:,.0f}"


def pct(value):
    return f"{value:+.2f}%"


def percentage_change(old, new):

    if old == 0:
        if new == 0:
            return 0.0
        return 100.0

    return ((new - old) / abs(old)) * 100


def clean_columns(data):

    data = data.copy()

    data.columns = (
        data.columns
        .astype(str)
        .str.strip()
    )

    return data


def numeric_column(data, column):

    if column not in data.columns:

        return pd.Series(
            0.0,
            index=data.index
        )

    return pd.to_numeric(
        data[column],
        errors="coerce"
    ).fillna(0)


# ============================================================
# FILE LOADER
# ============================================================

def load_year_file(year):

    year = str(year)

    possible_paths = [

        f"dmart_orders_{year}.csv",

        f"dmart_order_{year}.csv",

        f"dmart_{year}.csv",

        os.path.join(
            "backend",
            f"dmart_orders_{year}.csv"
        ),

        os.path.join(
            "backend",
            f"dmart_order_{year}.csv"
        ),

        os.path.join(
            "backend",
            f"dmart_{year}.csv"
        ),
    ]

    file_path = None

    for path in possible_paths:

        if os.path.exists(path):

            file_path = path
            break

    if file_path is None:

        raise FileNotFoundError(
            f"Could not find DMart file for {year}."
        )

    data = pd.read_csv(file_path)

    return clean_columns(data)


# ============================================================
# BASIC SUMMARY
# ============================================================

def build_summary(data):

    amount = numeric_column(
        data,
        "Amount"
    )

    profit = numeric_column(
        data,
        "Profit"
    )

    quantity = numeric_column(
        data,
        "Quantity"
    )

    sales = amount.sum()

    total_profit = profit.sum()

    total_quantity = quantity.sum()

    orders = len(data)

    margin = (
        total_profit / sales * 100
        if sales != 0
        else 0
    )

    return {

        "sales": float(sales),

        "profit": float(total_profit),

        "quantity": float(total_quantity),

        "orders": int(orders),

        "margin": float(margin)
    }


# ============================================================
# DIMENSION DRIVER ANALYSIS
# ============================================================

def analyse_dimension(
    old_data,
    new_data,
    column,
    metric="Amount"
):

    if column not in old_data.columns:
        return None

    if column not in new_data.columns:
        return None

    old = old_data.copy()
    new = new_data.copy()

    old[column] = (
        old[column]
        .astype(str)
        .str.strip()
    )

    new[column] = (
        new[column]
        .astype(str)
        .str.strip()
    )

    old["_metric"] = numeric_column(
        old,
        metric
    )

    new["_metric"] = numeric_column(
        new,
        metric
    )

    old_group = (
        old.groupby(column)["_metric"]
        .sum()
    )

    new_group = (
        new.groupby(column)["_metric"]
        .sum()
    )

    items = (
        set(old_group.index)
        | set(new_group.index)
    )

    if not items:
        return None

    rows = []

    for item in items:

        old_value = float(
            old_group.get(item, 0)
        )

        new_value = float(
            new_group.get(item, 0)
        )

        change = (
            new_value - old_value
        )

        change_pct = percentage_change(
            old_value,
            new_value
        )

        rows.append({

            "item": str(item),

            "old": old_value,

            "new": new_value,

            "change": change,

            "change_pct": change_pct
        })

    result = pd.DataFrame(rows)

    if result.empty:
        return None

    return result.sort_values(
        "change",
        ascending=False
    ).reset_index(drop=True)


# ============================================================
# TOP DRIVERS
# ============================================================

def get_drivers(
    old_data,
    new_data,
    column,
    metric="Amount",
    top_n=5
):

    result = analyse_dimension(
        old_data,
        new_data,
        column,
        metric
    )

    if result is None:
        return None

    improvements = (
        result[result["change"] > 0]
        .head(top_n)
    )

    declines = (
        result[result["change"] < 0]
        .sort_values(
            "change",
            ascending=True
        )
        .head(top_n)
    )

    return {

        "all": result,

        "improvements": improvements,

        "declines": declines
    }


# ============================================================
# MONTH DRIVER
# ============================================================

def month_driver(
    old_data,
    new_data,
    metric="Amount"
):

    if (
        "Date" not in old_data.columns
        or "Date" not in new_data.columns
    ):
        return None

    old = old_data.copy()
    new = new_data.copy()

    old["_date"] = pd.to_datetime(
        old["Date"],
        errors="coerce"
    )

    new["_date"] = pd.to_datetime(
        new["Date"],
        errors="coerce"
    )

    old["_month"] = (
        old["_date"]
        .dt.month
    )

    new["_month"] = (
        new["_date"]
        .dt.month
    )

    old["_metric"] = numeric_column(
        old,
        metric
    )

    new["_metric"] = numeric_column(
        new,
        metric
    )

    old_group = (
        old.groupby("_month")["_metric"]
        .sum()
    )

    new_group = (
        new.groupby("_month")["_metric"]
        .sum()
    )

    rows = []

    for month in range(1, 13):

        old_value = float(
            old_group.get(month, 0)
        )

        new_value = float(
            new_group.get(month, 0)
        )

        rows.append({

            "month": month,

            "old": old_value,

            "new": new_value,

            "change":
                new_value - old_value,

            "change_pct":
                percentage_change(
                    old_value,
                    new_value
                )
        })

    return pd.DataFrame(rows)


# ============================================================
# NEW / REMOVED ITEMS
# ============================================================

def detect_new_removed(
    old_data,
    new_data,
    column
):

    if (
        column not in old_data.columns
        or column not in new_data.columns
    ):
        return None

    old_items = set(
        old_data[column]
        .dropna()
        .astype(str)
        .str.strip()
    )

    new_items = set(
        new_data[column]
        .dropna()
        .astype(str)
        .str.strip()
    )

    return {

        "new":
            sorted(
                new_items - old_items
            ),

        "removed":
            sorted(
                old_items - new_items
            )
    }


# ============================================================
# VOLUME VS PRICE ANALYSIS
# ============================================================

def volume_price_analysis(
    old_data,
    new_data
):

    old_amount = numeric_column(
        old_data,
        "Amount"
    )

    new_amount = numeric_column(
        new_data,
        "Amount"
    )

    old_quantity = numeric_column(
        old_data,
        "Quantity"
    )

    new_quantity = numeric_column(
        new_data,
        "Quantity"
    )

    old_sales = old_amount.sum()
    new_sales = new_amount.sum()

    old_qty = old_quantity.sum()
    new_qty = new_quantity.sum()

    old_avg = (
        old_sales / old_qty
        if old_qty != 0
        else 0
    )

    new_avg = (
        new_sales / new_qty
        if new_qty != 0
        else 0
    )

    return {

        "old_avg_value":
            old_avg,

        "new_avg_value":
            new_avg,

        "avg_change":
            new_avg - old_avg,

        "avg_change_pct":
            percentage_change(
                old_avg,
                new_avg
            ),

        "quantity_change":
            new_qty - old_qty,

        "quantity_change_pct":
            percentage_change(
                old_qty,
                new_qty
            )
    }


# ============================================================
# ROOT CAUSE CLASSIFICATION
# ============================================================

def classify_root_cause(
    old_summary,
    new_summary,
    volume_price
):

    sales_change = (
        new_summary["sales"]
        - old_summary["sales"]
    )

    profit_change = (
        new_summary["profit"]
        - old_summary["profit"]
    )

    quantity_change = (
        volume_price[
            "quantity_change"
        ]
    )

    avg_change = (
        volume_price[
            "avg_change"
        ]
    )

    reasons = []

    # --------------------------------------------------------
    # SALES
    # --------------------------------------------------------

    if sales_change > 0:

        if (
            quantity_change > 0
            and avg_change > 0
        ):

            reasons.append(
                "Sales growth was driven by both "
                "higher quantity and higher average order value."
            )

        elif quantity_change > 0:

            reasons.append(
                "Sales growth was mainly driven by "
                "higher sales volume."
            )

        elif avg_change > 0:

            reasons.append(
                "Sales growth was mainly driven by "
                "higher average value per unit."
            )

        else:

            reasons.append(
                "Sales increased despite lower "
                "volume and average value, indicating "
                "a mix or transaction-level effect."
            )

    elif sales_change < 0:

        if (
            quantity_change < 0
            and avg_change < 0
        ):

            reasons.append(
                "Sales decline was driven by both "
                "lower quantity and lower average value."
            )

        elif quantity_change < 0:

            reasons.append(
                "Sales decline was mainly driven by "
                "lower sales volume."
            )

        elif avg_change < 0:

            reasons.append(
                "Sales decline was mainly driven by "
                "lower average value per unit."
            )

        else:

            reasons.append(
                "Sales declined despite positive volume "
                "or average-value movement, indicating "
                "a product or market-mix effect."
            )

    # --------------------------------------------------------
    # PROFIT
    # --------------------------------------------------------

    if profit_change < 0:

        reasons.append(
            "Profit declined, suggesting margin pressure "
            "or weaker profitability of the sales mix."
        )

    elif profit_change > 0:

        reasons.append(
            "Profit increased overall."
        )

    return reasons


# ============================================================
# FORMAT DRIVER
# ============================================================

def format_driver(
    row,
    money_value=True
):

    item = row["item"]

    change = row["change"]

    change_pct = row["change_pct"]

    if money_value:

        old_text = money(row["old"])
        new_text = money(row["new"])
        change_text = money(abs(change))

    else:

        old_text = number(row["old"])
        new_text = number(row["new"])
        change_text = number(abs(change))

    arrow = (
        "↑"
        if change > 0
        else "↓"
        if change < 0
        else "→"
    )

    return (
        f"{item}: "
        f"{old_text} → {new_text} "
        f"({arrow} {change_text}, "
        f"{pct(change_pct)})"
    )


# ============================================================
# MAIN ROOT CAUSE ENGINE
# ============================================================

def root_cause_analysis(
    old_file,
    new_file,
    old_year=None,
    new_year=None
):

    old_data = load_year_file(
        old_year
    ) if old_file is None else pd.read_csv(
        old_file
    )

    new_data = load_year_file(
        new_year
    ) if new_file is None else pd.read_csv(
        new_file
    )

    old_data = clean_columns(
        old_data
    )

    new_data = clean_columns(
        new_data
    )

    if old_year is None:
        old_year = 2024

    if new_year is None:
        new_year = 2025

    old_summary = build_summary(
        old_data
    )

    new_summary = build_summary(
        new_data
    )

    volume_price = (
        volume_price_analysis(
            old_data,
            new_data
        )
    )

    reasons = classify_root_cause(
        old_summary,
        new_summary,
        volume_price
    )

    # ========================================================
    # DIMENSION DRIVERS
    # ========================================================

    product = get_drivers(
        old_data,
        new_data,
        "Product",
        "Amount"
    )

    city = get_drivers(
        old_data,
        new_data,
        "City",
        "Amount"
    )

    category = get_drivers(
        old_data,
        new_data,
        "Category",
        "Profit"
    )

    months = month_driver(
        old_data,
        new_data,
        "Amount"
    )

    # ========================================================
    # NEW / REMOVED
    # ========================================================

    product_status = detect_new_removed(
        old_data,
        new_data,
        "Product"
    )

    city_status = detect_new_removed(
        old_data,
        new_data,
        "City"
    )

    category_status = detect_new_removed(
        old_data,
        new_data,
        "Category"
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    answer = (
        "🔎 ROOT CAUSE ANALYSIS\n\n"
        f"🗓️ {old_year} → {new_year}\n\n"
    )

    # --------------------------------------------------------
    # BUSINESS MOVEMENT
    # --------------------------------------------------------

    answer += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 BUSINESS MOVEMENT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"Sales: "
        f"{money(old_summary['sales'])} → "
        f"{money(new_summary['sales'])}\n"

        f"Profit: "
        f"{money(old_summary['profit'])} → "
        f"{money(new_summary['profit'])}\n"

        f"Quantity: "
        f"{number(old_summary['quantity'])} → "
        f"{number(new_summary['quantity'])}\n"

        f"Margin: "
        f"{old_summary['margin']:.2f}% → "
        f"{new_summary['margin']:.2f}%\n\n"
    )

    # --------------------------------------------------------
    # ROOT CAUSES
    # --------------------------------------------------------

    answer += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 ROOT CAUSES\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if reasons:

        for reason in reasons:

            answer += (
                f"• {reason}\n"
            )

    else:

        answer += (
            "• No major root cause detected.\n"
        )

    answer += "\n"

    # --------------------------------------------------------
    # VOLUME / VALUE
    # --------------------------------------------------------

    answer += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 VOLUME vs VALUE\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"Average value per unit:\n"
        f"{old_year}: "
        f"{money(volume_price['old_avg_value'])}\n"

        f"{new_year}: "
        f"{money(volume_price['new_avg_value'])}\n"

        f"Change: "
        f"{pct(volume_price['avg_change_pct'])}\n\n"

        f"Quantity change: "
        f"{pct(volume_price['quantity_change_pct'])}\n\n"
    )

    # --------------------------------------------------------
    # PRODUCT ROOT CAUSE
    # --------------------------------------------------------

    if product:

        answer += (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🛒 PRODUCT DRIVERS\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if not product["improvements"].empty:

            answer += "📈 Positive drivers:\n"

            for _, row in product[
                "improvements"
            ].head(5).iterrows():

                answer += (
                    f"• {format_driver(row)}\n"
                )

            answer += "\n"

        if not product["declines"].empty:

            answer += "📉 Negative drivers:\n"

            for _, row in product[
                "declines"
            ].head(5).iterrows():

                answer += (
                    f"• {format_driver(row)}\n"
                )

            answer += "\n"

    # --------------------------------------------------------
    # CITY ROOT CAUSE
    # --------------------------------------------------------

    if city:

        answer += (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🏙️ CITY DRIVERS\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if not city["improvements"].empty:

            answer += "📈 Positive city drivers:\n"

            for _, row in city[
                "improvements"
            ].head(5).iterrows():

                answer += (
                    f"• {format_driver(row)}\n"
                )

            answer += "\n"

        if not city["declines"].empty:

            answer += "📉 Negative city drivers:\n"

            for _, row in city[
                "declines"
            ].head(5).iterrows():

                answer += (
                    f"• {format_driver(row)}\n"
                )

            answer += "\n"

    # --------------------------------------------------------
    # CATEGORY ROOT CAUSE
    # --------------------------------------------------------

    if category:

        answer += (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 CATEGORY PROFIT DRIVERS\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if not category["improvements"].empty:

            answer += "📈 Profit drivers:\n"

            for _, row in category[
                "improvements"
            ].head(5).iterrows():

                answer += (
                    f"• {format_driver(row)}\n"
                )

            answer += "\n"

        if not category["declines"].empty:

            answer += "📉 Profit pressure:\n"

            for _, row in category[
                "declines"
            ].head(5).iterrows():

                answer += (
                    f"• {format_driver(row)}\n"
                )

            answer += "\n"

    # --------------------------------------------------------
    # MONTH ROOT CAUSE
    # --------------------------------------------------------

    if months is not None:

        best_month = months.loc[
            months["new"].idxmax()
        ]

        worst_month = months.loc[
            months["change"].idxmin()
        ]

        best_improvement = months.loc[
            months["change"].idxmax()
        ]

        answer += (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📅 MONTHLY ROOT CAUSE\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"🏆 Strongest month in "
            f"{new_year}: "
            f"{int(best_month['month'])}\n"

            f"📈 Biggest improvement: "
            f"Month {int(best_improvement['month'])} "
            f"({pct(best_improvement['change_pct'])})\n"

            f"📉 Biggest decline: "
            f"Month {int(worst_month['month'])} "
            f"({pct(worst_month['change_pct'])})\n\n"
        )

    # --------------------------------------------------------
    # NEW / REMOVED
    # --------------------------------------------------------

    if product_status:

        if product_status["new"]:

            answer += (
                "🆕 New products: "
                + ", ".join(
                    product_status["new"]
                )
                + "\n"
            )

        if product_status["removed"]:

            answer += (
                "❌ Removed products: "
                + ", ".join(
                    product_status["removed"]
                )
                + "\n"
            )

        answer += "\n"

    if city_status:

        if city_status["new"]:

            answer += (
                "🆕 New cities: "
                + ", ".join(
                    city_status["new"]
                )
                + "\n"
            )

        if city_status["removed"]:

            answer += (
                "❌ Removed cities: "
                + ", ".join(
                    city_status["removed"]
                )
                + "\n"
            )

        answer += "\n"

    if category_status:

        if category_status["new"]:

            answer += (
                "🆕 New categories: "
                + ", ".join(
                    category_status["new"]
                )
                + "\n"
            )

        if category_status["removed"]:

            answer += (
                "❌ Removed categories: "
                + ", ".join(
                    category_status["removed"]
                )
                + "\n"
            )

        answer += "\n"

    # --------------------------------------------------------
    # FINAL ROOT CAUSE
    # --------------------------------------------------------

    answer += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧠 MANAGEMENT INTERPRETATION\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    sales_change = (
        new_summary["sales"]
        - old_summary["sales"]
    )

    profit_change = (
        new_summary["profit"]
        - old_summary["profit"]
    )

    margin_change = (
        new_summary["margin"]
        - old_summary["margin"]
    )

    if (
        sales_change > 0
        and profit_change > 0
        and margin_change >= 0
    ):

        answer += (
            "✅ Growth appears healthy because "
            "sales, profit and margin improved."
        )

    elif (
        sales_change > 0
        and profit_change > 0
        and margin_change < 0
    ):

        answer += (
            "⚠️ Business is growing, but margin pressure "
            "is reducing the quality of that growth."
        )

    elif (
        sales_change < 0
        and profit_change < 0
    ):

        answer += (
            "🔴 The business experienced broad deterioration. "
            "Both revenue and profitability weakened."
        )

    elif (
        sales_change < 0
        and profit_change > 0
    ):

        answer += (
            "⚠️ Revenue weakened, but profitability improved. "
            "This suggests a potentially healthier sales mix "
            "or stronger cost control."
        )

    else:

        answer += (
            "➡️ Performance was mixed. "
            "The strongest positive and negative drivers "
            "should be investigated before making decisions."
        )

    return answer


# ============================================================
# APP.PY COMPATIBILITY
# ============================================================

def root_cause_files(
    old_file,
    new_file,
    old_year=2024,
    new_year=2025
):

    return root_cause_analysis(
        old_file=old_file,
        new_file=new_file,
        old_year=old_year,
        new_year=new_year
    )


def root_cause_years(
    year1="2024",
    year2="2025"
):

    return root_cause_analysis(
        old_file=None,
        new_file=None,
        old_year=year1,
        new_year=year2
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "\n===== PHASE 5.5 ROOT CAUSE ENGINE =====\n"
    )

    try:

        result = root_cause_years(
            "2024",
            "2025"
        )

        print(result)

    except Exception as error:

        print(
            "❌ Root Cause Engine Error:",
            repr(error)
        )