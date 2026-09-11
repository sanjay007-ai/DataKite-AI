# ============================================================
# CONTEXT MANAGER — PHASE 5.2
# Context-Aware AI
# ============================================================

# Stores the current conversation context
_context = {
    "current_file": None,
    "previous_question": None,
    "previous_answer": None,
    "conversation_history": []
}


# ============================================================
# SET CURRENT FILE
# ============================================================

def set_current_file(file_name):
    """
    Store the currently uploaded/active file.
    """
    _context["current_file"] = file_name


# ============================================================
# GET CURRENT FILE
# ============================================================

def get_current_file():
    """
    Return the currently active file.
    """
    return _context["current_file"]


# ============================================================
# SAVE QUESTION + ANSWER
# ============================================================

def save_context(question, answer):
    """
    Save the latest question and answer.
    """

    _context["previous_question"] = str(question)

    _context["previous_answer"] = str(answer)

    _context["conversation_history"].append({
        "question": str(question),
        "answer": str(answer)
    })


# ============================================================
# GET PREVIOUS QUESTION
# ============================================================

def get_previous_question():
    """
    Return the previous question.
    """
    return _context["previous_question"]


# ============================================================
# GET PREVIOUS ANSWER
# ============================================================

def get_previous_answer():
    """
    Return the previous answer.
    """
    return _context["previous_answer"]


# ============================================================
# GET CONVERSATION HISTORY
# ============================================================

def get_history():
    """
    Return complete conversation history.
    """
    return _context["conversation_history"]


# ============================================================
# GET LAST CONTEXT
# ============================================================

def get_context():
    """
    Return the complete current context.
    """

    return {
        "current_file": _context["current_file"],
        "previous_question": _context["previous_question"],
        "previous_answer": _context["previous_answer"]
    }


# ============================================================
# BUILD CONTEXT FOR AI
# ============================================================

def build_context():
    """
    Create a clean context string that can later
    be passed to the AI engine.
    """

    current_file = _context["current_file"]
    previous_question = _context["previous_question"]
    previous_answer = _context["previous_answer"]

    context = []

    context.append("===== AI CONTEXT =====")

    if current_file:
        context.append(
            f"Current File: {current_file}"
        )
    else:
        context.append(
            "Current File: None"
        )

    if previous_question:
        context.append(
            f"Previous Question: {previous_question}"
        )
    else:
        context.append(
            "Previous Question: None"
        )

    if previous_answer:
        context.append(
            f"Previous Answer: {previous_answer}"
        )
    else:
        context.append(
            "Previous Answer: None"
        )

    context.append("======================")

    return "\n".join(context)


# ============================================================
# CLEAR CONTEXT
# ============================================================

def clear_context():
    """
    Clear all conversation context.
    """

    _context["current_file"] = None
    _context["previous_question"] = None
    _context["previous_answer"] = None
    _context["conversation_history"] = []


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("\n===== PHASE 5.2 CONTEXT TEST =====\n")

    # Current uploaded file
    set_current_file("dmart_orders.csv")

    # First question
    question1 = "What are the total sales?"

    answer1 = "Total Sales = ₹692,992,727"

    save_context(question1, answer1)

    print("Current File:")
    print(get_current_file())

    print("\nPrevious Question:")
    print(get_previous_question())

    print("\nPrevious Answer:")
    print(get_previous_answer())

    print("\nContext Summary:")
    print(build_context())

    # Follow-up question
    question2 = "Which city performed best?"

    answer2 = "Chennai performed best."

    save_context(question2, answer2)

    print("\n===== AFTER FOLLOW-UP =====\n")

    print(build_context())

    print("\n===== CONVERSATION HISTORY =====\n")

    for item in get_history():

        print("Question:", item["question"])
        print("Answer:", item["answer"])
        print("-" * 40)