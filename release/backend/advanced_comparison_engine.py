import os
import pandas as pd


# ============================================================
# PHASE 5.4.2 — ADVANCED COMPARISON ENGINE
# ============================================================


def money(value):
    return f"₹{value:,.2f}"


def percent(value):
    return f"{value:+.2f}%"

def load_year_file(year):
    """
    Load yearly DMart CSV.

    Actual files:
        dmart_orders_2024.csv
        dmart_orders_2025.csv
    """

    possible_paths = [
        f"dmart_orders_{year}.csv",
        f"Dmart_orders_{year}.csv",
        f"Dmart order {year}.csv",
        f"dmart_order_{year}.csv",
        f"dmart_{year}.csv",
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

    data.columns = (
        data.columns
        .astype(str)
        .str.strip()
    )

    return data
    
def prepare_data(data):
    """
    Clean numeric columns.
    """

    data = data.copy()

    numeric_columns = [
        "Amount",
        "Profit",
        "Quantity"
    ]

    for column in numeric_columns:

        if column in data.columns:

            data[column] = (
                data[column]
                .astype(str)
                .str.replace("₹", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce"
            ).fillna(0)

    return data


def get_year_summary(data):

    sales = data["Amount"].sum()

    profit = data["Profit"].sum()

    quantity = data["Quantity"].sum()

    orders = len(data)

    margin = (
        (profit / sales) * 100
        if sales != 0
        else 0
    )

    return {
        "sales": sales,
        "profit": profit,
        "quantity": quantity,
        "orders": orders,
        "margin": margin
    }


def change_value(old, new):

    difference = new - old

    if old != 0:
        percentage_change = (
            difference / abs(old)
        ) * 100
    else:
        percentage_change = 0

    return difference, percentage_change


def compare_dimension(
    old_data,
    new_data,
    column
):

    if column not in old_data.columns:
        return None

    if column not in new_data.columns:
        return None

    old_result = (
        old_data
        .groupby(column)["Amount"]
        .sum()
    )

    new_result = (
        new_data
        .groupby(column)["Amount"]
        .sum()
    )

    common = set(old_result.index) & set(new_result.index)

    if not common:
        return None

    changes = []

    for item in common:

        old_value = old_result[item]
        new_value = new_result[item]

        difference, change = change_value(
            old_value,
            new_value
        )

        changes.append({
            "name": item,
            "old": old_value,
            "new": new_value,
            "difference": difference,
            "change": change
        })

    return changes


def best_and_worst(changes):

    if not changes:
        return None, None

    best = max(
        changes,
        key=lambda x: x["difference"]
    )

    worst = min(
        changes,
        key=lambda x: x["difference"]
    )

    return best, worst


def highest_item(data, column, metric="Amount"):

    if column not in data.columns:
        return None

    result = (
        data
        .groupby(column)[metric]
        .sum()
        .sort_values(ascending=False)
    )

    if result.empty:
        return None

    return result.index[0], result.iloc[0]


def compare_years(year1, year2):

    old_data = prepare_data(
        load_year_file(year1)
    )

    new_data = prepare_data(
        load_year_file(year2)
    )

    old = get_year_summary(old_data)

    new = get_year_summary(new_data)

    sales_diff, sales_change = change_value(
        old["sales"],
        new["sales"]
    )

    profit_diff, profit_change = change_value(
        old["profit"],
        new["profit"]
    )

    quantity_diff, quantity_change = change_value(
        old["quantity"],
        new["quantity"]
    )

    order_diff, order_change = change_value(
        old["orders"],
        new["orders"]
    )

    margin_diff = (
        new["margin"] - old["margin"]
    )

    # ========================================================
    # PRODUCT ANALYSIS
    # ========================================================

    product_changes = compare_dimension(
        old_data,
        new_data,
        "Product"
    )

    best_product = None
    worst_product = None

    if product_changes:
        best_product, worst_product = best_and_worst(
            product_changes
        )

    highest_product = highest_item(
        new_data,
        "Product",
        "Amount"
    )

    # ========================================================
    # CITY ANALYSIS
    # ========================================================

    city_changes = compare_dimension(
        old_data,
        new_data,
        "City"
    )

    best_city = None
    worst_city = None

    if city_changes:
        best_city, worst_city = best_and_worst(
            city_changes
        )

    highest_city = highest_item(
        new_data,
        "City",
        "Amount"
    )

    # ========================================================
    # CATEGORY ANALYSIS
    # ========================================================

    category_changes = compare_dimension(
        old_data,
        new_data,
        "Category"
    )

    best_category = None
    worst_category = None

    if category_changes:
        best_category, worst_category = best_and_worst(
            category_changes
        )

    highest_profit_category = highest_item(
        new_data,
        "Category",
        "Profit"
    )

    # ========================================================
    # MONTH ANALYSIS
    # ========================================================

    month_changes = compare_dimension(
        old_data,
        new_data,
        "Month"
    )

    best_month = None
    worst_month = None

    if month_changes:
        best_month, worst_month = best_and_worst(
            month_changes
        )

    # ========================================================
    # BUSINESS CONCLUSION
    # ========================================================

    conclusion = []

    if sales_diff > 0:
        conclusion.append(
            f"✅ Sales increased by {sales_change:.2f}%."
        )
    elif sales_diff < 0:
        conclusion.append(
            f"⚠️ Sales decreased by {abs(sales_change):.2f}%."
        )
    else:
        conclusion.append(
            "➡️ Sales remained unchanged."
        )

    if profit_diff > 0:
        conclusion.append(
            f"✅ Profit increased by {profit_change:.2f}%."
        )
    elif profit_diff < 0:
        conclusion.append(
            f"🔴 Profit decreased by {abs(profit_change):.2f}%."
        )

    if margin_diff < 0:
        conclusion.append(
            f"⚠️ Profit margin declined by "
            f"{abs(margin_diff):.2f} percentage points."
        )
    elif margin_diff > 0:
        conclusion.append(
            f"📈 Profit margin improved by "
            f"{margin_diff:.2f} percentage points."
        )

    # ========================================================
    # FINAL REPORT
    # ========================================================

    answer = (
        "📊 ADVANCED BUSINESS COMPARISON\n\n"
        f"🗓️ {year1} vs {year2}\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 SALES PERFORMANCE\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"{year1}: {money(old['sales'])}\n"
        f"{year2}: {money(new['sales'])}\n"
        f"Change: {'↑' if sales_diff >= 0 else '↓'} "
        f"{money(abs(sales_diff))} "
        f"({sales_change:+.2f}%)\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📈 PROFIT PERFORMANCE\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"{year1}: {money(old['profit'])}\n"
        f"{year2}: {money(new['profit'])}\n"
        f"Change: {'↑' if profit_diff >= 0 else '↓'} "
        f"{money(abs(profit_diff))} "
        f"({profit_change:+.2f}%)\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 QUANTITY PERFORMANCE\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"{year1}: {old['quantity']:,.0f} units\n"
        f"{year2}: {new['quantity']:,.0f} units\n"
        f"Change: {quantity_diff:+,.0f} "
        f"({quantity_change:+.2f}%)\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧾 ORDER PERFORMANCE\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"{year1}: {old['orders']:,} orders\n"
        f"{year2}: {new['orders']:,} orders\n"
        f"Change: {order_diff:+,} orders\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 PROFIT MARGIN\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"{year1}: {old['margin']:.2f}%\n"
        f"{year2}: {new['margin']:.2f}%\n"
        f"Margin change: {margin_diff:+.2f} percentage points\n\n"
    )

    # Product
    if highest_product:

        answer += (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🛒 PRODUCT ANALYSIS\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏆 Highest-sales product in {year2}: "
            f"{highest_product[0]} — "
            f"{money(highest_product[1])}\n"
        )

    if best_product:

        answer += (
            f"📈 Biggest improvement: "
            f"{best_product['name']} "
            f"({best_product['change']:+.2f}%)\n"
        )

    if worst_product:

        answer += (
            f"📉 Biggest decline: "
            f"{worst_product['name']} "
            f"({worst_product['change']:+.2f}%)\n\n"
        )

    # City
    if highest_city:

        answer += (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🏙️ CITY ANALYSIS\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏆 Best city in {year2}: "
            f"{highest_city[0]} — "
            f"{money(highest_city[1])}\n"
        )

    if best_city:

        answer += (
            f"📈 Biggest improvement: "
            f"{best_city['name']} "
            f"({best_city['change']:+.2f}%)\n"
        )

    if worst_city:

        answer += (
            f"📉 Biggest decline: "
            f"{worst_city['name']} "
            f"({worst_city['change']:+.2f}%)\n\n"
        )

    # Category
    if highest_profit_category:

        answer += (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 CATEGORY PROFIT ANALYSIS\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏆 Most profitable category in {year2}: "
            f"{highest_profit_category[0]} — "
            f"{money(highest_profit_category[1])}\n\n"
        )

    # Month
    if best_month or worst_month:

        answer += (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📅 MONTH ANALYSIS\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if best_month:
            answer += (
                f"📈 Strongest improvement: "
                f"{best_month['name']} "
                f"({best_month['change']:+.2f}%)\n"
            )

        if worst_month:
            answer += (
                f"📉 Biggest decline: "
                f"{worst_month['name']} "
                f"({worst_month['change']:+.2f}%)\n\n"
            )

    answer += (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 BUSINESS CONCLUSION\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(conclusion)
    )

    return answer


# ============================================================
# APP.PY COMPATIBILITY FUNCTION
# ============================================================

def advanced_compare_files(year1, year2):
    """
    Compatibility wrapper used by app.py.
    """

    return compare_years(
        year1,
        year2
    )

# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        compare_years(
            "2024",
            "2025"
        )
    )