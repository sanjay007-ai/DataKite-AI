import re
import pandas as pd
from csv_reader import get_data, load_csv


def get_dataset():
    data = get_data()

    if data is None:
        return None

    data = data.copy()
    data.columns = data.columns.str.strip()

    return data


def money(value):
    return f"₹{value:,.2f}"


def find_column_values(data, item1, item2):
    """
    Find which CSV column contains both comparison values.
    Priority:
    City → Product → Category → Month → Customer
    """

    columns = [
        "City",
        "Product",
        "Category",
        "Month",
        "Customer"
    ]

    item1 = str(item1).strip().lower()
    item2 = str(item2).strip().lower()

    for column in columns:

        if column not in data.columns:
            continue

        values = (
            data[column]
            .dropna()
            .astype(str)
            .str.strip()
        )

        value_map = {
            value.lower(): value
            for value in values.unique()
        }

        if item1 in value_map and item2 in value_map:
            return column, value_map[item1], value_map[item2]

    return None, None, None


def compare_values(column, value1, value2):

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    required = ["Amount", "Profit"]

    missing = [
        col for col in required
        if col not in data.columns
    ]

    if missing:
        return f"❌ Missing columns: {', '.join(missing)}"

    # Match values case-insensitively
    filtered = data[
        data[column]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin([
            str(value1).lower(),
            str(value2).lower()
        ])
    ].copy()

    if filtered.empty:
        return (
            f"❌ No data found for "
            f"'{value1}' and '{value2}'."
        )

    result = (
        filtered.groupby(column)
        .agg(
            Sales=("Amount", "sum"),
            Profit=("Profit", "sum"),
            Orders=("Amount", "count")
        )
    )

    real_values = {
        str(value).lower(): value
        for value in result.index
    }

    real_value1 = real_values.get(str(value1).lower())
    real_value2 = real_values.get(str(value2).lower())

    if real_value1 is None or real_value2 is None:
        return (
            f"❌ Could not find '{value1}' "
            f"and '{value2}' in the CSV."
        )

    a = result.loc[real_value1]
    b = result.loc[real_value2]

    if a["Sales"] > b["Sales"]:
        winner = real_value1
    elif b["Sales"] > a["Sales"]:
        winner = real_value2
    else:
        winner = "Both"

    if column == "City":
        title = "🏙️ CITY COMPARISON"
    elif column == "Product":
        title = "📦 PRODUCT COMPARISON"
    elif column == "Category":
        title = "🛒 CATEGORY COMPARISON"
    elif column == "Month":
        title = "📅 MONTH COMPARISON"
    elif column == "Customer":
        title = "👤 CUSTOMER COMPARISON"
    else:
        title = f"📊 {column.upper()} COMPARISON"

    return (
        f"{title}\n\n"

        f"🔵 {real_value1}\n"
        f"Sales: {money(a['Sales'])}\n"
        f"Profit: {money(a['Profit'])}\n"
        f"Orders: {int(a['Orders']):,}\n\n"

        f"🟢 {real_value2}\n"
        f"Sales: {money(b['Sales'])}\n"
        f"Profit: {money(b['Profit'])}\n"
        f"Orders: {int(b['Orders']):,}\n\n"

        f"🏆 Better by Sales: {winner}"
    )


def get_comparison_insight(question):

    question = str(question).strip()

    match = re.search(
        r"^\s*compare\s+(.+?)\s+(?:and|vs|versus)\s+(.+?)\s*$",
        question,
        re.IGNORECASE
    )

    if not match:
        return None

    item1 = match.group(1).strip()
    item2 = match.group(2).strip()

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    column, value1, value2 = find_column_values(
        data,
        item1,
        item2
    )

    if column is None:
        return (
            f"❌ Could not find '{item1}' and '{item2}' "
            "as comparable values in the CSV."
        )

    print(
        f"🔎 Comparison detected: "
        f"{column} → {value1} vs {value2}"
    )

    return compare_values(
        column,
        value1,
        value2
    )


# ==================================================
# 🧪 TEST PHASE 5.4
# ==================================================

if __name__ == "__main__":

    print("\n===== PHASE 5.4 COMPARISON ENGINE =====\n")

    try:
        load_csv("dmart_orders.csv")
        print("✅ DMart CSV loaded successfully.\n")

    except Exception as e:
        print(f"❌ CSV loading failed: {e}")
        exit()

    test_questions = [
        "Compare Chennai and Mumbai",
        "Compare Electronics and Grocery",
        "Compare January and February"
    ]

    for question in test_questions:

        print("QUESTION:")
        print(question)

        answer = get_comparison_insight(question)

        print("\nANSWER:")
        print(answer)

        print("\n" + "=" * 60 + "\n")