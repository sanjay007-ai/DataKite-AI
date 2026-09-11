# ============================================================
# QUESTION ENGINE — PHASE 5.1
# Advanced Question Understanding
# ============================================================

import re


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_question(question):
    """
    Clean the user's question for intent detection.
    """
    if question is None:
        return ""

    question = str(question).strip().lower()

    # Remove extra spaces
    question = re.sub(r"\s+", " ", question)

    # Remove unnecessary punctuation
    question = question.rstrip("?!.")

    return question


# ============================================================
# INTENT DETECTION
# ============================================================

def detect_intent(question):

    question = clean_question(question)

    # --------------------------------------------------------
    # EMPTY QUESTION
    # --------------------------------------------------------

    if not question:
        return "unknown"


    # --------------------------------------------------------
    # GREETING
    # --------------------------------------------------------

    greeting_words = [
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening"
    ]

    if question in greeting_words:
        return "greeting"


    # --------------------------------------------------------
    # WHY / ROOT CAUSE
    # --------------------------------------------------------

    why_patterns = [
        "why did",
        "why is",
        "why are",
        "why was",
        "why were",
        "why has",
        "why have",
        "what caused",
        "reason for",
        "cause of",
        "what is causing"
    ]

    if any(pattern in question for pattern in why_patterns):
        return "why"


    # --------------------------------------------------------
    # RECOMMENDATION
    # --------------------------------------------------------

    recommendation_patterns = [
        "how can i improve",
        "how can we improve",
        "how to improve",
        "what should i do",
        "what should we do",
        "what should the business improve",
        "give me recommendations",
        "give me 5 recommendations",
        "recommendations",
        "recommend",
        "suggest",
        "suggestions"
    ]

    if any(pattern in question for pattern in recommendation_patterns):
        return "recommendation"


    # --------------------------------------------------------
    # RISK
    # --------------------------------------------------------

    risk_patterns = [
        "business risks",
        "what are the risks",
        "what risks",
        "risk analysis",
        "identify risks",
        "where are the risks"
    ]

    if any(pattern in question for pattern in risk_patterns):
        return "risk"


    # --------------------------------------------------------
    # OPPORTUNITY
    # --------------------------------------------------------

    opportunity_patterns = [
        "business opportunities",
        "where are the opportunities",
        "what are the opportunities",
        "find opportunities",
        "identify opportunities",
        "growth opportunities",
        "opportunity analysis"
    ]

    if any(pattern in question for pattern in opportunity_patterns):
        return "opportunity"


    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    comparison_patterns = [
        "compare",
        "comparison",
        "versus",
        "vs",
        "difference between",
        "which is better",
        "which performed better",
        "better than",
        "higher than",
        "lower than"
    ]

    if any(pattern in question for pattern in comparison_patterns):
        return "comparison"


    # --------------------------------------------------------
    # SALES ANALYSIS
    # --------------------------------------------------------

    sales_patterns = [
        "total sales",
        "overall sales",
        "sales",
        "sales analysis",
        "sales performance",
        "sales trend",
        "sales growth",
        "sales decline",
        "sales decreased",
        "sales increased",
        "sales dropped",
        "sales went down",
        "sales went up"
    ]

    if any(pattern in question for pattern in sales_patterns):
        return "sales"


    # --------------------------------------------------------
    # PROFIT ANALYSIS
    # --------------------------------------------------------

    profit_patterns = [
        "total profit",
        "overall profit",
        "profit",
        "profit analysis",
        "profit performance",
        "profit margin",
        "profit growth",
        "profit decline",
        "profit increased",
        "profit decreased",
        "profit low",
        "profit high"
    ]

    if any(pattern in question for pattern in profit_patterns):
        return "profit"


    # --------------------------------------------------------
    # PRODUCT ANALYSIS
    # --------------------------------------------------------

    product_patterns = [
        "product",
        "products",
        "best product",
        "best performing product",
        "best selling product",
        "which product sold the most",
        "top product",
        "top products",
        "most sold product",
        "product performance"
    ]

    if any(pattern in question for pattern in product_patterns):
        return "product"


    # --------------------------------------------------------
    # CITY ANALYSIS
    # --------------------------------------------------------

    city_patterns = [
        "city",
        "cities",
        "best city",
        "top city",
        "which city performed best",
        "highest sales city",
        "city performance",
        "city analysis"
    ]

    if any(pattern in question for pattern in city_patterns):
        return "city"


    # --------------------------------------------------------
    # CUSTOMER ANALYSIS
    # --------------------------------------------------------

    customer_patterns = [
        "customer",
        "customers",
        "best customer",
        "top customer",
        "customer performance",
        "customer analysis",
        "customer retention"
    ]

    if any(pattern in question for pattern in customer_patterns):
        return "customer"


    # --------------------------------------------------------
    # CATEGORY ANALYSIS
    # --------------------------------------------------------

    category_patterns = [
        "category",
        "categories",
        "best category",
        "top category",
        "category performance",
        "category analysis",
        "most profitable category"
    ]

    if any(pattern in question for pattern in category_patterns):
        return "category"


    # --------------------------------------------------------
    # GENERAL INSIGHT
    # --------------------------------------------------------

    insight_patterns = [
        "insight",
        "insights",
        "important insight",
        "key insight",
        "business insight",
        "business insights",
        "summarize",
        "summary",
        "overall performance",
        "what is happening",
        "what do you notice"
    ]

    if any(pattern in question for pattern in insight_patterns):
        return "insight"


    # --------------------------------------------------------
    # DATASET INFORMATION
    # --------------------------------------------------------

    dataset_patterns = [
        "what is this file about",
        "what is this dataset about",
        "summarize this file",
        "how many rows",
        "how many columns",
        "column names",
        "what are the columns",
        "important points",
        "dataset information",
        "dataset summary"
    ]

    if any(pattern in question for pattern in dataset_patterns):
        return "dataset"


    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return "unknown"


# ============================================================
# QUESTION ANALYSIS
# ============================================================

def analyze_question(question):

    cleaned = clean_question(question)

    intent = detect_intent(cleaned)

    return {
        "question": question,
        "clean_question": cleaned,
        "intent": intent,
        "is_comparison": intent == "comparison",
        "is_why": intent == "why",
        "is_recommendation": intent == "recommendation",
        "is_risk": intent == "risk",
        "is_opportunity": intent == "opportunity",
        "is_analytics": intent in [
            "sales",
            "profit",
            "product",
            "city",
            "customer",
            "category",
            "insight"
        ]
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_questions = [

        "What are the total sales?",

        "Which product sold the most?",

        "Which city performed best?",

        "Why did sales decrease?",

        "Why is profit low?",

        "Why is Product A performing better?",

        "Compare Chennai and Mumbai",

        "Compare Product A and Product B",

        "Compare January and February",

        "How can I improve sales?",

        "How can I improve profit?",

        "Give me 5 recommendations",

        "What are the business risks?",

        "Where are the opportunities?",

        "What are the most important insights?",
    ]


    print("\n===== PHASE 5.1 QUESTION ENGINE TEST =====\n")

    for question in test_questions:

        result = analyze_question(question)

        print(f"Question : {question}")
        print(f"Intent   : {result['intent']}")
        print("-" * 50)