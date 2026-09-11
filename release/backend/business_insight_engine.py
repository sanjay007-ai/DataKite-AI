# ============================================================
# BUSINESS INSIGHT ENGINE — PHASE 5.3
# ============================================================

import pandas as pd
from csv_reader import get_data, load_csv


# ============================================================
# HELPERS
# ============================================================

def get_dataset():
    data = get_data()

    if data is None:
        return None

    data = data.copy()
    data.columns = data.columns.str.strip()

    return data


def money(value):
    return f"₹{value:,.2f}"


def safe_group_sum(data, group_column, value_column):
    if group_column not in data.columns:
        return None

    if value_column not in data.columns:
        return None

    return (
        data.groupby(group_column)[value_column]
        .sum()
        .sort_values(ascending=False)
    )


# ============================================================
# 1. BEST-SELLING PRODUCT
# ============================================================

def best_selling_product():

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    if "Product" not in data.columns or "Quantity" not in data.columns:
        return "❌ Product or Quantity column is missing."

    result = (
        data.groupby("Product")["Quantity"]
        .sum()
        .sort_values(ascending=False)
    )

    product = result.index[0]
    quantity = result.iloc[0]

    return (
        f"Your best-selling product is **{product}**, "
        f"with {quantity:,} units sold. 🛒"
    )


# ============================================================
# 2. BEST CITY
# ============================================================

def best_city():

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    if "City" not in data.columns or "Amount" not in data.columns:
        return "❌ City or Amount column is missing."

    result = (
        data.groupby("City")["Amount"]
        .sum()
        .sort_values(ascending=False)
    )

    city = result.index[0]
    sales = result.iloc[0]

    return (
        f"**{city}** is your top-performing city, "
        f"bringing in {money(sales)} in sales. 🏙️"
    )


# ============================================================
# 3. BEST CUSTOMER
# ============================================================

def best_customer():

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    if "Customer" not in data.columns or "Amount" not in data.columns:
        return "❌ Customer or Amount column is missing."

    result = (
        data.groupby("Customer")["Amount"]
        .sum()
        .sort_values(ascending=False)
    )

    customer = result.index[0]
    sales = result.iloc[0]

    return (
        f"Your top customer is **{customer}**, "
        f"having spent {money(sales)} with you so far. 👤"
    )


# ============================================================
# 4. BEST MONTH
# ============================================================

def best_month():

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    if "Month" not in data.columns or "Amount" not in data.columns:
        return "❌ Month or Amount column is missing."

    result = (
        data.groupby("Month")["Amount"]
        .sum()
        .sort_values(ascending=False)
    )

    month = result.index[0]
    sales = result.iloc[0]

    return (
        f"**{month}** was your strongest month, "
        f"with {money(sales)} in sales. 📅"
    )


# ============================================================
# 5. MOST PROFITABLE CATEGORY
# ============================================================

def most_profitable_category():

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    if "Category" not in data.columns or "Profit" not in data.columns:
        return "❌ Category or Profit column is missing."

    result = (
        data.groupby("Category")["Profit"]
        .sum()
        .sort_values(ascending=False)
    )

    category = result.index[0]
    profit = result.iloc[0]

    return (
        f"**{category}** is your most profitable category, "
        f"generating {money(profit)} in profit. 💎"
    )


# ============================================================
# 6. TOP 5 PRODUCTS
# ============================================================

def top_products(limit=5):

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    if "Product" not in data.columns or "Quantity" not in data.columns:
        return "❌ Product or Quantity column is missing."

    result = (
        data.groupby("Product")["Quantity"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )

    output = "🏆 TOP PRODUCTS\n\n"

    for i, (product, quantity) in enumerate(
        result.items(),
        start=1
    ):
        output += (
            f"{i}. {product} — "
            f"{quantity:,} units\n"
        )

    return output.rstrip()


# ============================================================
# 7. TOP 5 CITIES
# ============================================================

def top_cities(limit=5):

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    if "City" not in data.columns or "Amount" not in data.columns:
        return "❌ City or Amount column is missing."

    result = (
        data.groupby("City")["Amount"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )

    output = "🏙️ TOP CITIES BY SALES\n\n"

    for i, (city, sales) in enumerate(
        result.items(),
        start=1
    ):
        output += (
            f"{i}. {city} — "
            f"{money(sales)}\n"
        )

    return output.rstrip()


# ============================================================
# 8. TOP 5 CATEGORIES
# ============================================================

def top_categories(limit=5):

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    if "Category" not in data.columns or "Amount" not in data.columns:
        return "❌ Category or Amount column is missing."

    result = (
        data.groupby("Category")["Amount"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )

    output = "📦 TOP CATEGORIES BY SALES\n\n"

    for i, (category, sales) in enumerate(
        result.items(),
        start=1
    ):
        output += (
            f"{i}. {category} — "
            f"{money(sales)}\n"
        )

    return output.rstrip()


# ============================================================
# 9. TOP 5 PROFITABLE PRODUCTS
# ============================================================

def top_profitable_products(limit=5):

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    if "Product" not in data.columns or "Profit" not in data.columns:
        return "❌ Product or Profit column is missing."

    result = (
        data.groupby("Product")["Profit"]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )

    output = "💎 TOP PROFITABLE PRODUCTS\n\n"

    for i, (product, profit) in enumerate(
        result.items(),
        start=1
    ):
        output += (
            f"{i}. {product} — "
            f"{money(profit)}\n"
        )

    return output.rstrip()


# ============================================================
# 10. OVERALL KPI INSIGHTS
# ============================================================

def overall_kpi_insights():

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    output = "Here's how your business is performing overall:\n\n"

    if "Amount" in data.columns:
        total_sales = data["Amount"].sum()
        average_sales = data["Amount"].mean()

        output += (
            f"💰 Total Sales: {money(total_sales)}\n"
            f"🧾 Average Order Value: {money(average_sales)}\n"
        )

    if "Profit" in data.columns:
        total_profit = data["Profit"].sum()

        output += (
            f"📈 Total Profit: {money(total_profit)}\n"
        )

        if "Amount" in data.columns and total_sales != 0:
            margin = (total_profit / total_sales) * 100

            output += (
                f"📊 Profit Margin: {margin:.2f}%\n"
            )

    if "Quantity" in data.columns:
        output += (
            f"📦 Total Quantity: "
            f"{data['Quantity'].sum():,}\n"
        )

    output += (
        f"📄 Total Orders: {len(data):,}\n"
    )

    if "Customer" in data.columns:
        output += (
            f"👤 Unique Customers: "
            f"{data['Customer'].nunique():,}\n"
        )

    return output.rstrip()


# ============================================================
# 11. IMPORTANT BUSINESS INSIGHTS
# ============================================================

def important_insights():

    data = get_dataset()

    if data is None:
        return "❌ Please upload a CSV file first."

    insights = []

    # --------------------------------------------------------
    # Sales
    # --------------------------------------------------------

    if "Amount" in data.columns:

        total_sales = data["Amount"].sum()

        insights.append(
            f"💰 Total sales generated: "
            f"{money(total_sales)}"
        )

    # --------------------------------------------------------
    # Profit
    # --------------------------------------------------------

    if "Profit" in data.columns:

        total_profit = data["Profit"].sum()

        insights.append(
            f"📈 Total profit generated: "
            f"{money(total_profit)}"
        )

    # --------------------------------------------------------
    # Best Product
    # --------------------------------------------------------

    if (
        "Product" in data.columns
        and "Quantity" in data.columns
    ):

        products = (
            data.groupby("Product")["Quantity"]
            .sum()
            .sort_values(ascending=False)
        )

        best_product = products.index[0]

        insights.append(
            f"🛒 Best-selling product: "
            f"{best_product} "
            f"({products.iloc[0]:,} units)"
        )

    # --------------------------------------------------------
    # Best City
    # --------------------------------------------------------

    if (
        "City" in data.columns
        and "Amount" in data.columns
    ):

        cities = (
            data.groupby("City")["Amount"]
            .sum()
            .sort_values(ascending=False)
        )

        best_city_name = cities.index[0]

        insights.append(
            f"🏙️ Top-performing city: "
            f"{best_city_name} "
            f"({money(cities.iloc[0])})"
        )

    # --------------------------------------------------------
    # Best Category
    # --------------------------------------------------------

    if (
        "Category" in data.columns
        and "Profit" in data.columns
    ):

        categories = (
            data.groupby("Category")["Profit"]
            .sum()
            .sort_values(ascending=False)
        )

        best_category = categories.index[0]

        insights.append(
            f"💎 Most profitable category: "
            f"{best_category} "
            f"({money(categories.iloc[0])})"
        )

    # --------------------------------------------------------
    # Best Customer
    # --------------------------------------------------------

    if (
        "Customer" in data.columns
        and "Amount" in data.columns
    ):

        customers = (
            data.groupby("Customer")["Amount"]
            .sum()
            .sort_values(ascending=False)
        )

        best_customer_name = customers.index[0]

        insights.append(
            f"👤 Highest-value customer: "
            f"{best_customer_name} "
            f"({money(customers.iloc[0])})"
        )

    # --------------------------------------------------------
    # Best Month
    # --------------------------------------------------------

    if (
        "Month" in data.columns
        and "Amount" in data.columns
    ):

        months = (
            data.groupby("Month")["Amount"]
            .sum()
            .sort_values(ascending=False)
        )

        insights.append(
            f"📅 Best sales month: "
            f"{months.index[0]} "
            f"({money(months.iloc[0])})"
        )

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    output = "💡 KEY BUSINESS INSIGHTS\n\n"

    for i, insight in enumerate(insights, start=1):
        output += f"{i}. {insight}\n"

    return output.rstrip()


# ============================================================
# MAIN BUSINESS INSIGHT ROUTER
# ============================================================

def get_business_insight(question):

    question = str(question).strip().lower()

    # --------------------------------------------------------
    # PRODUCT
    # --------------------------------------------------------

    if (
        "which product sold the most" in question
        or "best selling product" in question
        or "best-selling product" in question
        or "top product" in question
        or "most sold product" in question
    ):
        return best_selling_product()

    # --------------------------------------------------------
    # CITY
    # --------------------------------------------------------

    if (
        "which city performed best" in question
        or "best city" in question
        or "top city" in question
        or "highest sales city" in question
    ):
        return best_city()

    # --------------------------------------------------------
    # CUSTOMER
    # --------------------------------------------------------

    if (
        "best customer" in question
        or "top customer" in question
    ):
        return best_customer()

    # --------------------------------------------------------
    # MONTH
    # --------------------------------------------------------

    if (
        "best month" in question
        or "top month" in question
    ):
        return best_month()

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    if (
        "most profitable category" in question
        or "best category" in question
    ):
        return most_profitable_category()

    # --------------------------------------------------------
    # TOP LISTS
    # --------------------------------------------------------

    if "top 5 products" in question:
        return top_products(5)

    if "top 5 cities" in question:
        return top_cities(5)

    if "top 5 categories" in question:
        return top_categories(5)

    if "top 5 profitable products" in question:
        return top_profitable_products(5)

    # --------------------------------------------------------
    # GENERAL INSIGHTS
    # --------------------------------------------------------

    if (
        "important insights" in question
        or "key insights" in question
        or "business insights" in question
        or "most important insight" in question
    ):
        return important_insights()

    # --------------------------------------------------------
    # OVERALL PERFORMANCE
    # --------------------------------------------------------

    if (
        "overall performance" in question
        or "business performance" in question
        or "performance summary" in question
    ):
        return overall_kpi_insights()

    return None


# ============================================================
# TEST
# ============================================================

# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("\n===== PHASE 5.3 BUSINESS INSIGHT ENGINE =====\n")

    try:
        load_csv("dmart_orders.csv")
        print("✅ DMart CSV loaded successfully.\n")
    except Exception as e:
        print(f"❌ CSV loading failed: {e}")
        exit()

    test_questions = [
        "Which product sold the most?",
        "Which city performed best?",
        "What is the best customer?",
        "What is the best month?",
        "Which category is most profitable?",
        "Show top 5 products",
        "Show top 5 cities",
        "Show top 5 categories",
        "Show top 5 profitable products",
        "What are the most important insights?",
        "Show overall performance"
    ]

    for question in test_questions:

        print("QUESTION:")
        print(question)

        answer = get_business_insight(question)

        print("\nANSWER:")
        print(answer)

        print("\n" + "=" * 60 + "\n")