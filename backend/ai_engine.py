import pandas as pd
import re
from csv_reader import get_data


# ============================================================
# TEXT CLEANING HELPER
# ============================================================

def clean_text(value):
    return str(value).strip().lower()


# ============================================================
# HELPERS
# ============================================================

def numeric_columns(data):
    return data.select_dtypes(include="number").columns.tolist()


def text_columns(data):
    return data.select_dtypes(
        include=["object", "string"]
    ).columns.tolist()


def format_number(value):
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return str(value)


def find_date_columns(data):

    date_columns = []

    for column in data.columns:

        try:
            converted = pd.to_datetime(
                data[column],
                errors="coerce"
            )

            valid_ratio = converted.notna().mean()

            if valid_ratio >= 0.70:
                date_columns.append(column)

        except Exception:
            pass

    return date_columns


def find_column(data, possible_names):

    column_map = {
        clean_text(column): column
        for column in data.columns
    }

    for name in possible_names:

        if clean_text(name) in column_map:
            return column_map[clean_text(name)]
    return None
# ============================================================
# 4.1 — GENERATE BUSINESS REPORT
# ============================================================

def generate_report():

    data = get_data()

    if data is None:
        return "❌ Please upload a CSV file first."

    report = []

    report.append("📊 BUSINESS ANALYTICS REPORT")
    report.append("=" * 45)

    # --------------------------------------------------------
    # DATASET OVERVIEW
    # --------------------------------------------------------

    report.append("\n📄 DATASET OVERVIEW")
    report.append(f"Total Rows: {len(data):,}")
    report.append(f"Total Columns: {len(data.columns):,}")

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------

    report.append("\n📌 KEY PERFORMANCE INDICATORS")

    if "Amount" in data.columns:
        report.append(
            f"💰 Total Sales: ₹{data['Amount'].sum():,.2f}"
        )

    if "Profit" in data.columns:
        report.append(
            f"📈 Total Profit: ₹{data['Profit'].sum():,.2f}"
        )

    report.append(
        f"📄 Total Orders: {len(data):,}"
    )

    if "Quantity" in data.columns:
        report.append(
            f"📦 Total Quantity: {data['Quantity'].sum():,}"
        )

    if "Customer" in data.columns:
        report.append(
            f"👤 Unique Customers: "
            f"{data['Customer'].nunique():,}"
        )

    # --------------------------------------------------------
    # TOP PERFORMANCE
    # --------------------------------------------------------

    report.append("\n🏆 TOP PERFORMANCE")

    if "Customer" in data.columns and "Amount" in data.columns:
        top_customer = (
            data.groupby("Customer")["Amount"]
            .sum()
            .idxmax()
        )
        report.append(
            f"👤 Best Customer: {top_customer}"
        )

    if "Product" in data.columns and "Quantity" in data.columns:
        best_product = (
            data.groupby("Product")["Quantity"]
            .sum()
            .idxmax()
        )
        report.append(
            f"🛒 Best Product: {best_product}"
        )

    if "City" in data.columns and "Amount" in data.columns:
        top_city = (
            data.groupby("City")["Amount"]
            .sum()
            .idxmax()
        )
        report.append(
            f"🏙️ Top City: {top_city}"
        )

    if "Month" in data.columns and "Amount" in data.columns:
        best_month = (
            data.groupby("Month")["Amount"]
            .sum()
            .idxmax()
        )
        report.append(
            f"📅 Best Month: {best_month}"
        )

    # --------------------------------------------------------
    # BUSINESS INSIGHTS
    # --------------------------------------------------------

    report.append("\n💡 BUSINESS INSIGHTS")

    if "Amount" in data.columns:
        report.append(
            f"• Overall sales generated: "
            f"₹{data['Amount'].sum():,.2f}"
        )

    if "Profit" in data.columns:
        report.append(
            f"• Overall profit generated: "
            f"₹{data['Profit'].sum():,.2f}"
        )

    if (
        "Amount" in data.columns
        and "Profit" in data.columns
    ):
        report.append(
            f"• Average order value: "
            f"₹{data['Amount'].mean():,.2f}"
        )

    report.append("\n✅ REPORT GENERATED SUCCESSFULLY")

    return "\n".join(report)

def ask_ai(question):

    question = str(question).strip().lower()

    print("Question received:", repr(question))

    # =========================================================
    # 1. GREETINGS
    # =========================================================

    greeting_words = {
        "hello",
        "hi",
        "hey",
        "greetings",
        "hi there"
    }

    if question in greeting_words:
        return "Hello bro! 👋"

    # =========================================================
    # 2. GENERAL AI QUESTIONS
    # =========================================================

    if "who are you" in question:
        return "I am your Data Analyst AI Assistant."

    elif "who created you" in question or "who made you" in question:
        return (
            "Designed and developed by Sanjay "
            "(AI-assisted coding support by ChatGPT)."
        )

    elif question == "sql" or "what is sql" in question:
        return (
            "SQL (Structured Query Language) is used to "
            "create, manage, and query databases."
        )

    elif question == "python" or "what is python" in question:
        return (
            "Python is a powerful, easy-to-learn programming "
            "language used for AI, Data Analysis, Web Development, "
            "Automation, and Machine Learning."
        )

    # =========================================================
    # 3. GET DATA
    # =========================================================

    data = get_data()

    if data is None:
        return "Please upload a CSV file first."

    # =========================================================
    # 3.1 — GENERATE REPORT
    # =========================================================

    if any(phrase in question for phrase in [
        "generate report",
        "create report",
        "business report",
        "complete report",
        "full report"
    ]):
        return generate_report()    

    # =========================================================
    # 4. BASIC DATASET INFORMATION
    # =========================================================

    if question in [
        "rows",
        "row",
        "how many rows",
        "number of rows",
        "total rows"
    ]:
        return f"📄 This CSV contains {len(data)} rows."

    elif question in [
        "columns",
        "column",
        "how many columns",
        "number of columns",
        "total columns"
    ]:
        return f"📑 This CSV contains {len(data.columns)} columns."

    elif question in [
        "column names",
        "what are the column names",
        "show column names",
        "list columns"
    ]:
        return "📑 Column Names:\n" + "\n".join(
            f"• {column}" for column in data.columns
        )

    # =========================================================
    # 5. CITY ANALYSIS - ALL CITIES
    # =========================================================

    if "City" in data.columns:

        cities = (
            data["City"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
        )

        matched_city = None

        # Check longest city names first
        for city in sorted(cities, key=len, reverse=True):

            city_clean = city.strip().lower()

            if city_clean and city_clean in question:
                matched_city = city
                break

        if matched_city:

            city_data = data[
                data["City"]
                .astype(str)
                .str.strip()
                .str.lower()
                == matched_city.strip().lower()
            ]

            if city_data.empty:
                return f"❌ No data found for {matched_city}."

            return (
            f"🏙️ {matched_city.upper()} ANALYSIS\n\n"
        f"📄 Orders: {len(city_data)}\n"
        f"💰 Sales: ₹{city_data['Amount'].sum():,.2f}\n"
        f"📈 Profit: ₹{city_data['Profit'].sum():,.2f}\n"
        f"📦 Quantity: {city_data['Quantity'].sum()}\n"
        f"👤 Customers: {city_data['Customer'].nunique()}"
        )

    # =========================================================
    # 6. SPECIFIC SALES ANALYSIS
    # =========================================================

    # Top 10 must come BEFORE generic "sales"
    if "top 10 sales" in question:

        top = (
            data.sort_values(
                "Amount",
                ascending=False
            )
            .head(10)
        )

        return "🏆 TOP 10 SALES\n\n" + top[
            ["OrderID", "Product", "City", "Amount", "Profit", "Status"]
        ].to_string(index=False)

    elif "total sales" in question or "overall sales" in question:

        return (
            f"💰 Total Sales = "
            f"₹{data['Amount'].sum():,.2f}"
        )

    elif "total revenue" in question or "overall revenue" in question:

        return (
            f"💰 Total Revenue = "
            f"₹{data['Amount'].sum():,.2f}"
        )

    elif "average sales" in question or \
         "average amount" in question or \
         "mean sales" in question:

        return (
            f"💰 Average Sales = "
            f"₹{data['Amount'].mean():,.2f}"
        )

    elif "total amount" in question:

        return (
            f"💰 Total Amount = "
            f"₹{data['Amount'].sum():,.2f}"
        )

    # =========================================================
    # 7. PROFIT ANALYSIS
    # =========================================================

    elif "total profit" in question:

        return (
            f"📈 Total Profit = "
            f"₹{data['Profit'].sum():,.2f}"
        )

    elif "highest profit" in question:

        row = data.loc[data["Profit"].idxmax()]

        return (
            f"📈 HIGHEST PROFIT\n\n"
            f"Product: {row['Product']}\n"
            f"Profit: ₹{row['Profit']:,.2f}"
        )

    elif "lowest profit" in question:

        row = data.loc[data["Profit"].idxmin()]

        return (
            f"📉 LOWEST PROFIT\n\n"
            f"Product: {row['Product']}\n"
            f"Profit: ₹{row['Profit']:,.2f}"
        )

    # =========================================================
    # 8. ORDER / QUANTITY / CUSTOMER
    # =========================================================

    elif (
        "total orders" in question
        or "number of orders" in question
        or question == "orders"
    ):

        return f"📄 Total Orders = {len(data)}"

    elif "total quantity" in question:

        return (
            f"📦 Total Quantity Sold = "
            f"{data['Quantity'].sum()}"
        )

    elif "total customers" in question or \
         "unique customers" in question:

        return (
            f"👤 Unique Customers = "
            f"{data['Customer'].nunique()}"
        )

    # =========================================================
    # 9. BEST SELLING PRODUCT
    # =========================================================

    elif (
        "best selling product" in question
        or question == "top product"
        or "best product" in question
    ):

        product_quantity = (
            data.groupby("Product")["Quantity"]
            .sum()
            .sort_values(ascending=False)
        )

        top_product = product_quantity.index[0]
        total_quantity = product_quantity.iloc[0]

        return (
            f"🛒 BEST SELLING PRODUCT\n\n"
            f"Product: {top_product}\n"
            f"Quantity Sold: {total_quantity}"
        )

    # =========================================================
    # 10. TOP 5 CUSTOMERS
    # =========================================================

    elif any(word in question for word in [
        "top 5 customers",
        "best customers",
        "highest customers",
        "top customers"
    ]):

        top5 = (
            data.groupby("Customer")["Amount"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        result = "🏆 TOP 5 CUSTOMERS\n\n"

        for i, (customer, amount) in enumerate(
            top5.items(),
            start=1
        ):
            result += (
                f"{i}. {customer} - "
                f"₹{amount:,.2f}\n"
            )

        return result

    # =========================================================
    # 11. TOP 5 PRODUCTS
    # =========================================================

    elif any(word in question for word in [
        "top 5 products",
        "best products",
        "top products",
        "highest products"
    ]):

        top5 = (
            data.groupby("Product")["Quantity"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        result = "🛒 TOP 5 PRODUCTS\n\n"

        for i, (product, qty) in enumerate(
            top5.items(),
            start=1
        ):
            result += (
                f"{i}. {product} - "
                f"{qty} units\n"
            )

        return result

    # =========================================================
    # 12. TOP 5 CITIES
    # =========================================================

    elif any(word in question for word in [
        "top 5 cities",
        "top cities",
        "best cities"
    ]):

        top5 = (
            data.groupby("City")["Amount"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        result = "🏙️ TOP 5 CITIES\n\n"

        for i, (city, amount) in enumerate(
            top5.items(),
            start=1
        ):
            result += (
                f"{i}. {city} - "
                f"₹{amount:,.2f}\n"
            )

        return result

    # =========================================================
    # 13. TOP 5 MONTHS
    # =========================================================

    elif any(word in question for word in [
        "top 5 months",
        "best months",
        "top months"
    ]):

        top5 = (
            data.groupby("Month")["Amount"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        result = "📅 TOP 5 MONTHS\n\n"

        for i, (month, amount) in enumerate(
            top5.items(),
            start=1
        ):
            result += (
                f"{i}. {month} - "
                f"₹{amount:,.2f}\n"
            )

        return result

    # =========================================================
    # 14. TOP 5 CATEGORIES
    # =========================================================

    elif any(word in question for word in [
        "top 5 categories",
        "best categories",
        "top categories"
    ]):

        top5 = (
            data.groupby("Category")["Amount"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        result = "📦 TOP 5 CATEGORIES\n\n"

        for i, (category, amount) in enumerate(
            top5.items(),
            start=1
        ):
            result += (
                f"{i}. {category} - "
                f"₹{amount:,.2f}\n"
            )

        return result

    # =========================================================
    # 15. TOP 5 PROFITABLE PRODUCTS
    # =========================================================

    elif any(word in question for word in [
        "top 5 profitable products",
        "best profitable products",
        "highest profit products"
    ]):

        top5 = (
            data.groupby("Product")["Profit"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        result = "💎 TOP 5 PROFITABLE PRODUCTS\n\n"

        for i, (product, profit) in enumerate(
            top5.items(),
            start=1
        ):
            result += (
                f"{i}. {product} - "
                f"₹{profit:,.2f}\n"
            )

        return result

    # =========================================================
    # 16. BOTTOM 5 CUSTOMERS
    # =========================================================

    elif any(word in question for word in [
        "bottom 5 customers",
        "lowest customers"
    ]):

        bottom5 = (
            data.groupby("Customer")["Amount"]
            .sum()
            .sort_values()
            .head(5)
        )

        result = "📉 BOTTOM 5 CUSTOMERS\n\n"

        for i, (customer, amount) in enumerate(
            bottom5.items(),
            start=1
        ):
            result += (
                f"{i}. {customer} - "
                f"₹{amount:,.2f}\n"
            )

        return result

    # =========================================================
    # 17. QUANTITY ANALYSIS
    # =========================================================

    elif any(word in question for word in [
        "quantity analysis",
        "top quantity",
        "highest quantity",
        "most sold",
        "top quantity products"
    ]):

        top5 = (
            data.groupby("Product")["Quantity"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )

        result = "📦 TOP 5 PRODUCTS BY QUANTITY\n\n"

        for i, (product, qty) in enumerate(
            top5.items(),
            start=1
        ):
            result += (
                f"{i}. {product} - "
                f"{qty} units\n"
            )

        return result

    # =========================================================
    # 18. PAYMENT ANALYSIS
    # =========================================================

    elif any(word in question for word in [
        "payment",
        "payment methods",
        "payment analysis"
    ]):

        payment = data["Payment"].value_counts()

        result = "💳 PAYMENT ANALYSIS\n\n"

        for method, count in payment.items():
            result += (
                f"{method}: {count}\n"
            )

        return result

    # =========================================================
    # 19. ORDER STATUS
    # =========================================================

    elif any(word in question for word in [
        "status",
        "order status",
        "status analysis"
    ]):

        status = data["Status"].value_counts()

        result = "📦 ORDER STATUS\n\n"

        for status_name, count in status.items():
            result += (
                f"{status_name}: {count}\n"
            )

        return result

    # =========================================================
    # 20. DEPARTMENT ANALYSIS
    # =========================================================

    elif any(word in question for word in [
        "department",
        "department analysis",
        "departments"
    ]):

        dept = data["Department"].value_counts()

        result = "🏢 DEPARTMENT ANALYSIS\n\n"

        for department, count in dept.items():
            result += (
                f"{department}: {count}\n"
            )

        return result

    # =========================================================
    # 21. MONTHLY SALES
    # =========================================================

    elif "monthly sales" in question:

        monthly = (
            data.groupby("Month")["Amount"]
            .sum()
        )

        return "📅 MONTHLY SALES\n\n" + monthly.to_string()

    # =========================================================
    # 22. SALES BY CITY
    # =========================================================

    elif "sales by city" in question:

        city_sales = (
            data.groupby("City")["Amount"]
            .sum()
            .sort_values(ascending=False)
        )

        return "🏙️ SALES BY CITY\n\n" + city_sales.to_string()

    # =========================================================
    # 23. BUSINESS INSIGHTS
    # =========================================================

    elif any(word in question for word in [
        "business insights",
        "insights",
        "summary",
        "report",
        "business analysis"
    ]):

        top_customer = (
            data.groupby("Customer")["Amount"]
            .sum()
            .idxmax()
        )

        top_city = (
            data.groupby("City")["Amount"]
            .sum()
            .idxmax()
        )

        top_product = (
            data.groupby("Product")["Quantity"]
            .sum()
            .idxmax()
        )

        top_month = (
            data.groupby("Month")["Amount"]
            .sum()
            .idxmax()
        )

        result = (
            f"📊 BUSINESS INSIGHTS\n\n"
            f"💰 Total Sales: ₹{data['Amount'].sum():,.2f}\n"
            f"📈 Total Profit: ₹{data['Profit'].sum():,.2f}\n"
            f"📦 Total Quantity: {data['Quantity'].sum()}\n"
            f"👤 Best Customer: {top_customer}\n"
            f"🛒 Best Product: {top_product}\n"
            f"🏙️ Best City: {top_city}\n"
            f"📅 Best Month: {top_month}\n"
            f"📄 Total Orders: {len(data)}\n\n"
            f"✅ Dataset is ready for analysis."
        )

        return result

    # =========================================================
    # 24. ADVANCED SMART SEARCH
    # =========================================================

    # ---------------------------------------------------------
    # Search helper
    # ---------------------------------------------------------

    def search_column(column_name, search_text):

        search_text = str(search_text).strip().casefold()

        values = (
            data[column_name]
            .dropna()
            .astype(str)
            .str.strip()
        )

        # Exact match first
        exact_matches = [
            value
            for value in values.unique()
            if value.casefold() == search_text
        ]

        if exact_matches:
            return exact_matches

        # Then allow "show Customer_567" / "Customer_567 details"
        matched_values = []

        for value in values.unique():

            if value.casefold() in search_text:
                matched_values.append(value)

        # Longest/exact-looking match first
            matched_values.sort(
            key=lambda x: len(x),
            reverse=True
        )

        return matched_values
    # ---------------------------------------------------------
    # PRODUCT SEARCH
    # Example:
    # Tea
    # Show Tea
    # Tea details
    # ---------------------------------------------------------

    matched_products = search_column("Product", question)

    if matched_products:

        product = matched_products[0]

        result = data[
            data["Product"]
            .astype(str)
            .str.strip()
            .str.lower()
            == product.lower()
        ]

        return (
            f"🔎 PRODUCT SEARCH\n\n"
            f"🛒 Product: {product}\n"
            f"📄 Orders: {len(result)}\n"
            f"💰 Sales: ₹{result['Amount'].sum():,.2f}\n"
            f"📈 Profit: ₹{result['Profit'].sum():,.2f}\n"
            f"📦 Quantity: {result['Quantity'].sum()}\n"
            f"👤 Customers: {result['Customer'].nunique()}"
        )


    # ---------------------------------------------------------
    # CUSTOMER SEARCH
    # Example:
    # Customer31
    # Show Customer31
    # Customer31 details
    # ---------------------------------------------------------

    matched_customers = search_column("Customer", question)

    if matched_customers:

        customer = matched_customers[0]

        result = data[
            data["Customer"]
            .astype(str)
            .str.strip()
            .str.lower()
            == customer.lower()
        ]

        return (
            f"🔎 CUSTOMER SEARCH\n\n"
            f"👤 Customer: {customer}\n"
            f"📄 Orders: {len(result)}\n"
            f"💰 Sales: ₹{result['Amount'].sum():,.2f}\n"
            f"📈 Profit: ₹{result['Profit'].sum():,.2f}\n"
            f"📦 Quantity: {result['Quantity'].sum()}"
        )


    # ---------------------------------------------------------
    # ORDER ID SEARCH
    # Example:
    # DM10647
    # Show DM10647
    # DM10647 details
    # ---------------------------------------------------------

    matched_orders = search_column("OrderID", question)

    if matched_orders:

        order_id = matched_orders[0]

        result = data[
            data["OrderID"]
            .astype(str)
            .str.strip()
            .str.lower()
            == order_id.lower()
        ]

        row = result.iloc[0]

        return (
            f"🔎 ORDER DETAILS\n\n"
            f"📄 Order ID: {row['OrderID']}\n"
            f"👤 Customer: {row['Customer']}\n"
            f"🏙️ City: {row['City']}\n"
            f"🛒 Product: {row['Product']}\n"
            f"🏷️ Category: {row['Category']}\n"
            f"📦 Quantity: {row['Quantity']}\n"
            f"💰 Amount: ₹{row['Amount']:,.2f}\n"
            f"📈 Profit: ₹{row['Profit']:,.2f}\n"
            f"💳 Payment: {row['Payment']}\n"
            f"📦 Status: {row['Status']}\n"
            f"📅 Date: {row['Date']}"
        )


    # ---------------------------------------------------------
    # CATEGORY SEARCH
    # Example:
    # Dairy
    # Beverages
    # Home Care
    # ---------------------------------------------------------

    matched_categories = search_column("Category", question)

    if matched_categories:

        category = matched_categories[0]

        result = data[
            data["Category"]
            .astype(str)
            .str.strip()
            .str.lower()
            == category.lower()
        ]

        return (
            f"🔎 CATEGORY ANALYSIS\n\n"
            f"🏷️ Category: {category}\n"
            f"📄 Orders: {len(result)}\n"
            f"💰 Sales: ₹{result['Amount'].sum():,.2f}\n"
            f"📈 Profit: ₹{result['Profit'].sum():,.2f}\n"
            f"📦 Quantity: {result['Quantity'].sum()}\n"
            f"👤 Customers: {result['Customer'].nunique()}"
        )
    # ========================================================
    # 8. ADVANCED MONTH + DATE SEARCH
    # ========================================================

    months = {
        "january": 1,
        "jan": 1,
        "february": 2,
        "feb": 2,
        "march": 3,
        "mar": 3,
        "april": 4,
        "apr": 4,
        "may": 5,
        "june": 6,
        "jun": 6,
        "july": 7,
        "jul": 7,
        "august": 8,
        "aug": 8,
        "september": 9,
        "sep": 9,
        "sept": 9,
        "october": 10,
        "oct": 10,
        "november": 11,
        "nov": 11,
        "december": 12,
        "dec": 12
    }


    # --------------------------------------------------------
    # FIND DATE COLUMN
    # --------------------------------------------------------

    date_column = None

    for column in data.columns:

        column_name = clean_text(column)

        if (
            "date" in column_name
            or "order date" in column_name
            or "transaction date" in column_name
            or "purchase date" in column_name
        ):
            date_column = column
            break


    # --------------------------------------------------------
    # FIND MONTH COLUMN
    # --------------------------------------------------------

    month_column = None

    for column in data.columns:

        column_name = clean_text(column)

        if "month" in column_name:
            month_column = column
            break


    # ========================================================
    # EXACT DATE SEARCH
    # ========================================================

    date_pattern = re.search(
        r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b",
        question
    )

    if date_pattern:

        user_date = date_pattern.group(1)

        parsed_user_date = pd.to_datetime(
            user_date,
            errors="coerce",
            dayfirst=False
        )

        # Try DD-MM-YYYY / DD/MM/YYYY
        if pd.isna(parsed_user_date):

            parsed_user_date = pd.to_datetime(
                user_date,
                errors="coerce",
                dayfirst=True
            )

        if pd.notna(parsed_user_date):

            if date_column:

                parsed_dates = pd.to_datetime(
                    data[date_column],
                    errors="coerce",
                    dayfirst=False
                )

                # Try day-first if needed
                if parsed_dates.notna().sum() == 0:

                    parsed_dates = pd.to_datetime(
                        data[date_column],
                        errors="coerce",
                        dayfirst=True
                    )

                result = data[
                    parsed_dates.dt.date
                    == parsed_user_date.date()
                ]

                if not result.empty:

                    numeric = numeric_columns(result)

                    # Show original CSV date format
                    actual_date = result[
                        date_column
                    ].iloc[0]

                    response = (
                        "📅 DATE ANALYSIS\n\n"
                        f"📅 Date: {actual_date}\n"
                        f"📄 Records: {len(result):,}\n"
                    )

                    for col in numeric[:5]:

                        response += (
                            f"📊 {col}: "
                            f"{format_number(result[col].sum())}\n"
                        )

                    return response

                else:

                    return (
                        "📅 DATE ANALYSIS\n\n"
                        f"❌ No records found for "
                        f"{user_date}."
                    )


    # ========================================================
    # MONTH SEARCH
    # ========================================================

    matched_month = None
    matched_month_name = None

    # Full names first
    for month_name, month_number in months.items():

        if len(month_name) >= 4:

            pattern = (
                r"\b"
                + re.escape(month_name)
                + r"\b"
            )

            if re.search(pattern, question):

                matched_month = month_number
                matched_month_name = month_name
                break


    # Short names if full name not found
    if matched_month is None:

        for month_name, month_number in months.items():

            if len(month_name) < 4:

                pattern = (
                    r"\b"
                    + re.escape(month_name)
                    + r"\b"
                )

                if re.search(pattern, question):

                    matched_month = month_number
                    matched_month_name = month_name
                    break


    if matched_month is not None:

        result = None


        # ----------------------------------------------------
        # OPTION 1: MONTH COLUMN
        # ----------------------------------------------------

        if month_column:

            month_values = (
                data[month_column]
                .astype(str)
                .str.strip()
                .str.lower()
            )

            month_names_for_number = [
                name
                for name, number in months.items()
                if number == matched_month
            ]

            result = data[
                month_values.isin(
                    month_names_for_number
                )
            ]


        # ----------------------------------------------------
        # OPTION 2: DATE COLUMN
        # ----------------------------------------------------

        if (
            result is None
            and date_column
        ):

            parsed_dates = pd.to_datetime(
                data[date_column],
                errors="coerce",
                dayfirst=False
            )

            if parsed_dates.notna().sum() == 0:

                parsed_dates = pd.to_datetime(
                    data[date_column],
                    errors="coerce",
                    dayfirst=True
                )

            result = data[
                parsed_dates.dt.month
                == matched_month
            ]


        # ----------------------------------------------------
        # RETURN MONTH RESULT
        # ----------------------------------------------------

        if result is not None and not result.empty:

            numeric = numeric_columns(result)

            display_month = (
                pd.Timestamp(
                    year=2000,
                    month=matched_month,
                    day=1
                ).strftime("%B")
            )

            response = (
                f"📅 {display_month.upper()} ANALYSIS\n\n"
                f"📄 Records: {len(result):,}\n"
            )

            for col in numeric[:5]:

                response += (
                    f"📊 {col}: "
                    f"{format_number(result[col].sum())}\n"
                )

            return response

        else:

            return (
                f"📅 {matched_month_name.upper()} ANALYSIS\n\n"
                "❌ No records found for this month."
            )    
    # ---------------------------------------------------------
    # GENERAL SMART SEARCH
    # ---------------------------------------------------------

    search_words = [
        word.strip()
        for word in question.split()
        if len(word.strip()) > 1
    ]

    matched_rows = []

    for _, row in data.iterrows():

        row_text = " ".join(
            str(value).lower()
            for value in row.values
        )

        if all(word in row_text for word in search_words):
            matched_rows.append(row)

    if matched_rows:

        result = pd.DataFrame(matched_rows)

        display_columns = [
            "OrderID",
            "Date",
            "Customer",
            "City",
            "Product",
            "Amount",
            "Profit",
            "Status"
        ]

        display_columns = [
            column
            for column in display_columns
            if column in result.columns
        ]

        return (
            f"🔎 SMART SEARCH\n\n"
            f"Found {len(result)} matching record(s).\n\n"
            + result[display_columns]
            .head(20)
            .to_string(index=False)
        )

        return "🔎 No matching data found."
    # =========================================================
    # 25. DEFAULT
    # =========================================================

    else:
        return (
            "I'm not sure how to answer that from this dataset. "
            "Try asking about one of its columns directly, or check "
            "the suggested questions above for ideas."
        )


# =============================================================
# DATASET SUMMARY
# =============================================================

def dataset_summary():
    """
    Build a human-readable summary of the currently loaded dataset.

    Degrades gracefully: any DMart-style column (Amount, Profit,
    Quantity, Customer, Product, City, Month) that isn't present in
    the uploaded file is simply skipped instead of raising a
    KeyError, so uploading a differently-shaped CSV/Excel file
    doesn't crash the request.
    """

    data = get_data()

    if data is None:
        return "No CSV uploaded."

    if data.empty:
        return "⚠️ The uploaded file has no rows to analyze."

    lines = [
        f"Got it — I've loaded your dataset. It has "
        f"{len(data):,} rows and {len(data.columns)} columns. "
        f"Here's a quick snapshot:",
        "",
    ]

    def add_total(label, emoji, column):
        if column in data.columns:
            try:
                value = pd.to_numeric(
                    data[column], errors="coerce"
                ).sum()
                lines.append(f"{emoji} {label}: ₹{value:,.2f}")
            except Exception:
                pass

    def add_top(label, emoji, group_column, value_column, agg="sum"):
        if group_column in data.columns and value_column in data.columns:
            try:
                grouped = pd.to_numeric(
                    data[value_column], errors="coerce"
                ).groupby(data[group_column])
                result = grouped.sum() if agg == "sum" else grouped.count()
                if not result.empty:
                    lines.append(f"{emoji} {label}: {result.idxmax()}")
            except Exception:
                pass

    add_total("Total sales", "💰", "Amount")
    add_total("Total profit", "📈", "Profit")

    if "Quantity" in data.columns:
        try:
            qty = pd.to_numeric(data["Quantity"], errors="coerce").sum()
            lines.append(f"📦 Total quantity: {qty:,.0f}")
        except Exception:
            pass

    add_top("Top customer", "👤", "Customer", "Amount")
    add_top("Best-selling product", "🛒", "Product", "Quantity")
    add_top("Top city", "🏙️", "City", "Amount")
    add_top("Best month", "📅", "Month", "Amount")

    lines.append("")
    lines.append("Ask me anything about it — I'm ready when you are.")

    return "\n".join(lines)