# ============================================================
# 🔥 PHASE 5.6 — BUSINESS RECOMMENDATION ENGINE
# ============================================================
#
# Purpose:
# Convert business performance findings into actionable
# management recommendations.
#
# Works with:
#   • Sales
#   • Profit
#   • Quantity
#   • Profit margin
#   • Product drivers
#   • City drivers
#   • Category drivers
#   • Year-over-year performance
#
# This engine does NOT replace:
#   Advanced Comparison Engine
#   Root Cause Engine
#   Business Insight Engine
#
# It converts analytical findings into ACTIONS.
#
# ============================================================

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


def clean_columns(data):

    data = data.copy()

    data.columns = (
        data.columns
        .astype(str)
        .str.strip()
    )

    return data


# ============================================================
# BASIC BUSINESS SUMMARY
# ============================================================

def build_summary(data):

    data = clean_columns(data)

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

    sales = float(
        amount.sum()
    )

    total_profit = float(
        profit.sum()
    )

    total_quantity = float(
        quantity.sum()
    )

    margin = (
        total_profit / sales * 100
        if sales != 0
        else 0
    )

    return {

        "sales": sales,

        "profit": total_profit,

        "quantity": total_quantity,

        "orders": int(len(data)),

        "margin": float(margin)
    }


# ============================================================
# DIMENSION ANALYSIS
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

    old = clean_columns(
        old_data
    )

    new = clean_columns(
        new_data
    )

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

    rows = []

    for item in items:

        old_value = float(
            old_group.get(
                item,
                0
            )
        )

        new_value = float(
            new_group.get(
                item,
                0
            )
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

    if not rows:
        return None

    return (
        pd.DataFrame(rows)
        .sort_values(
            "change"
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# FIND TOP NEGATIVE / POSITIVE DRIVERS
# ============================================================

def top_negative_drivers(
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
        return []

    return (
        result[
            result["change"] < 0
        ]
        .sort_values(
            "change"
        )
        .head(top_n)
        .to_dict(
            "records"
        )
    )


def top_positive_drivers(
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
        return []

    return (
        result[
            result["change"] > 0
        ]
        .sort_values(
            "change",
            ascending=False
        )
        .head(top_n)
        .to_dict(
            "records"
        )
    )


# ============================================================
# RECOMMENDATION GENERATOR
# ============================================================

def generate_recommendations(
    old_summary,
    new_summary,
    old_data,
    new_data
):

    recommendations = []

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

    quantity_change = (
        new_summary["quantity"]
        - old_summary["quantity"]
    )

    # ========================================================
    # SALES RECOMMENDATIONS
    # ========================================================

    if sales_change < 0:

        recommendations.append({

            "priority": "HIGH",

            "area": "Sales",

            "recommendation":
                "Investigate the major sources of "
                "sales decline and prioritize recovery "
                "of the largest negative drivers.",

            "reason":
                f"Sales decreased by "
                f"{money(abs(sales_change))}."
        })

    elif sales_change > 0:

        recommendations.append({

            "priority": "MEDIUM",

            "area": "Sales",

            "recommendation":
                "Protect and scale the strongest sales "
                "drivers while monitoring whether growth "
                "is sustainable.",

            "reason":
                f"Sales increased by "
                f"{money(sales_change)}."
        })


    # ========================================================
    # PROFIT RECOMMENDATIONS
    # ========================================================

    if profit_change < 0:

        recommendations.append({

            "priority": "CRITICAL",

            "area": "Profit",

            "recommendation":
                "Review low-profit products, categories "
                "and locations. Focus on improving the "
                "profitability of the weakest contributors.",

            "reason":
                f"Profit decreased by "
                f"{money(abs(profit_change))}."
        })

    elif profit_change > 0:

        recommendations.append({

            "priority": "MEDIUM",

            "area": "Profit",

            "recommendation":
                "Continue investing in profitable products "
                "and locations while protecting current margins.",

            "reason":
                f"Profit increased by "
                f"{money(profit_change)}."
        })


    # ========================================================
    # MARGIN RECOMMENDATIONS
    # ========================================================

    if margin_change < 0:

        recommendations.append({

            "priority": "HIGH",

            "area": "Margin",

            "recommendation":
                "Review pricing, discounting, product mix "
                "and cost structure because profitability "
                "is weakening relative to sales.",

            "reason":
                f"Profit margin decreased by "
                f"{abs(margin_change):.2f} percentage points."
        })

    elif margin_change > 0:

        recommendations.append({

            "priority": "LOW",

            "area": "Margin",

            "recommendation":
                "Maintain the current profitable sales mix "
                "and identify opportunities to scale high-margin "
                "products.",

            "reason":
                f"Profit margin improved by "
                f"{margin_change:.2f} percentage points."
        })


    # ========================================================
    # QUANTITY RECOMMENDATIONS
    # ========================================================

    if quantity_change < 0:

        recommendations.append({

            "priority": "HIGH",

            "area": "Volume",

            "recommendation":
                "Investigate demand and order-volume decline "
                "in the weakest products and cities.",

            "reason":
                f"Quantity decreased by "
                f"{number(abs(quantity_change))} units."
        })

    elif quantity_change > 0:

        recommendations.append({

            "priority": "MEDIUM",

            "area": "Volume",

            "recommendation":
                "Use the increase in sales volume to identify "
                "products and locations with the strongest "
                "demand momentum.",

            "reason":
                f"Quantity increased by "
                f"{number(quantity_change)} units."
        })


    # ========================================================
    # CITY RECOMMENDATIONS
    # ========================================================

    city_negative = top_negative_drivers(
        old_data,
        new_data,
        "City",
        "Amount"
    )

    if city_negative:

        city_names = ", ".join(
            str(row["item"])
            for row in city_negative[:3]
        )

        recommendations.append({

            "priority": "HIGH",

            "area": "City",

            "recommendation":
                f"Investigate declining city performance, "
                f"especially {city_names}. Review demand, "
                f"product availability and local sales trends.",

            "reason":
                "These cities showed the largest negative "
                "sales movement."
        })


    # ========================================================
    # PRODUCT RECOMMENDATIONS
    # ========================================================

    product_negative = top_negative_drivers(
        old_data,
        new_data,
        "Product",
        "Amount"
    )

    if product_negative:

        product_names = ", ".join(
            str(row["item"])
            for row in product_negative[:3]
        )

        recommendations.append({

            "priority": "HIGH",

            "area": "Product",

            "recommendation":
                f"Review declining products such as "
                f"{product_names}. Check demand, pricing, "
                f"availability and product mix.",

            "reason":
                "These products contributed strongly to "
                "the negative sales movement."
        })


    # ========================================================
    # POSITIVE OPPORTUNITIES
    # ========================================================

    product_positive = top_positive_drivers(
        old_data,
        new_data,
        "Product",
        "Amount"
    )

    if product_positive:

        product_names = ", ".join(
            str(row["item"])
            for row in product_positive[:3]
        )

        recommendations.append({

            "priority": "MEDIUM",

            "area": "Growth Opportunity",

            "recommendation":
                f"Consider increasing focus on strong products "
                f"such as {product_names}.",

            "reason":
                "These products showed the strongest positive "
                "sales movement."
        })


    return recommendations

# ============================================================
# BUSINESS ANALYSIS — PHASE 6.8
# ============================================================

def business_analysis(
    old_data,
    new_data
):

    old_data = clean_columns(old_data)
    new_data = clean_columns(new_data)

    result = {
        "success": True,
        "top_areas": [],
        "worst_areas": [],
        "problems": [],
        "risks": [],
        "focus": []
    }

    # --------------------------------------------------------
    # TOP PERFORMING AREAS
    # --------------------------------------------------------

    for column in ["City", "Product", "Category"]:

        analysis = analyse_dimension(
            old_data,
            new_data,
            column,
            "Amount"
        )

        if analysis is not None and not analysis.empty:

            positive = (
                analysis[
                    analysis["change"] > 0
                ]
                .sort_values(
                    "change",
                    ascending=False
                )
                .head(3)
            )

            for _, row in positive.iterrows():

                result["top_areas"].append({
                    "area": column,
                    "name": str(row["item"]),
                    "change": round(
                        float(row["change"]),
                        2
                    ),
                    "change_pct": round(
                        float(row["change_pct"]),
                        2
                    )
                })

    # --------------------------------------------------------
    # WORST PERFORMING AREAS
    # --------------------------------------------------------

    for column in ["City", "Product", "Category"]:

        analysis = analyse_dimension(
            old_data,
            new_data,
            column,
            "Amount"
        )

        if analysis is not None and not analysis.empty:

            negative = (
                analysis[
                    analysis["change"] < 0
                ]
                .sort_values(
                    "change"
                )
                .head(3)
            )

            for _, row in negative.iterrows():

                result["worst_areas"].append({
                    "area": column,
                    "name": str(row["item"]),
                    "change": round(
                        float(row["change"]),
                        2
                    ),
                    "change_pct": round(
                        float(row["change_pct"]),
                        2
                    )
                })

    # --------------------------------------------------------
    # BUSINESS PROBLEMS
    # --------------------------------------------------------

    old_summary = build_summary(old_data)
    new_summary = build_summary(new_data)

    if new_summary["sales"] < old_summary["sales"]:

        result["problems"].append(
            "Sales are declining."
        )

    if new_summary["profit"] < old_summary["profit"]:

        result["problems"].append(
            "Profit is declining."
        )

    if new_summary["margin"] < old_summary["margin"]:

        result["problems"].append(
            "Profit margin is weakening."
        )

    if new_summary["quantity"] < old_summary["quantity"]:

        result["problems"].append(
            "Sales volume is declining."
        )

    # --------------------------------------------------------
    # RISKS
    # --------------------------------------------------------

    if new_summary["margin"] < old_summary["margin"]:

        result["risks"].append(
            "Margin pressure may reduce future profitability."
        )

    if result["worst_areas"]:

        result["risks"].append(
            "Declining cities, products or categories "
            "could negatively affect future sales."
        )

    # --------------------------------------------------------
    # MANAGEMENT FOCUS
    # --------------------------------------------------------

    if result["worst_areas"]:

        result["focus"].append(
            "Investigate the largest negative sales drivers."
        )

    if result["top_areas"]:

        result["focus"].append(
            "Protect and scale the strongest performing areas."
        )

    if new_summary["margin"] < old_summary["margin"]:

        result["focus"].append(
            "Protect profit margins through pricing, "
            "cost and product-mix review."
        )

    return result
# ============================================================
# MAIN ENGINE
# ============================================================

def business_recommendations(
    old_data,
    new_data,
    old_year=2024,
    new_year=2025
):

    old_data = clean_columns(
        old_data
    )

    new_data = clean_columns(
        new_data
    )

    old_summary = build_summary(
        old_data
    )

    new_summary = build_summary(
        new_data
    )

    recommendations = generate_recommendations(
        old_summary,
        new_summary,
        old_data,
        new_data
    )

    answer = (
        "💡 BUSINESS RECOMMENDATION ENGINE\n\n"
        f"🗓️ {old_year} → {new_year}\n\n"
    )

    answer += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 PERFORMANCE SNAPSHOT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    answer += (
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

    answer += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 RECOMMENDED ACTIONS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not recommendations:

        answer += (
            "• No major recommendation generated. "
            "Business performance appears relatively stable.\n"
        )

    else:

        for index, item in enumerate(
            recommendations,
            start=1
        ):

            answer += (
                f"{index}. "
                f"[{item['priority']}] "
                f"{item['area']}\n"

                f"   👉 {item['recommendation']}\n"

                f"   📌 Reason: "
                f"{item['reason']}\n\n"
            )


    answer += (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧠 MANAGEMENT PRIORITY\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if new_summary["profit"] < old_summary["profit"]:

        answer += (
            "🔴 First priority: protect profitability. "
            "Investigate the largest profit and sales "
            "drivers before expanding aggressively."
        )

    elif new_summary["sales"] < old_summary["sales"]:

        answer += (
            "🟠 First priority: recover sales volume. "
            "Focus on the weakest cities, products and "
            "categories."
        )

    elif (
        new_summary["sales"] > old_summary["sales"]
        and new_summary["profit"] > old_summary["profit"]
    ):

        answer += (
            "🟢 Business performance is improving. "
            "Scale the strongest products and cities while "
            "protecting profit margins."
        )

    else:

        answer += (
            "🟡 Performance is mixed. "
            "Management should focus on the largest "
            "negative drivers before making major decisions."
        )

    return answer


# ============================================================
# YEAR-BASED WRAPPER
# ============================================================

def load_year_data(year):

    from root_cause_engine import load_year_file

    return load_year_file(
        str(year)
    )


def business_recommendations_years(
    year1="2024",
    year2="2025"
):

    old_data = load_year_data(
        year1
    )

    new_data = load_year_data(
        year2
    )

    return business_recommendations(
        old_data,
        new_data,
        old_year=year1,
        new_year=year2
    )


# ============================================================
# FILE-BASED WRAPPER
# ============================================================

def business_recommendations_files(
    old_file,
    new_file,
    old_year=2024,
    new_year=2025
):

    old_data = pd.read_csv(
        old_file
    )

    new_data = pd.read_csv(
        new_file
    )

    return business_recommendations(
        old_data,
        new_data,
        old_year=old_year,
        new_year=new_year
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "\n===== PHASE 5.6 BUSINESS RECOMMENDATION ENGINE =====\n"
    )

    try:

        result = business_recommendations_years(
            "2024",
            "2025"
        )

        print(result)

    except Exception as error:

        print(
            "❌ Business Recommendation Engine Error:",
            repr(error)
        )