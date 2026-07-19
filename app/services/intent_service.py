"""
Intent Service — classifies an incoming message into one of the branches
shown in the architecture diagram:

  GREETING     — hi, hello, thanks, bye, small talk
  GENERAL_CHAT — casual conversation not about the pharmacy business
  BUSINESS     — profit, inventory, expiry, purchasing, sales, suppliers
  MEDICINE     — drug information, compliance, dosing policy, SOPs (RAG-heavy)
  MIXED        — combines business data AND knowledge-base lookup

This is a lightweight rule-based classifier, not a separate LLM call — it
keeps the pipeline fast and avoids burning an extra API round-trip just to
classify intent. It is intentionally conservative: anything ambiguous falls
through to BUSINESS or MIXED rather than GREETING, so a real question never
gets short-circuited into a throwaway small-talk reply.
"""

GREETING = "greeting"
GENERAL_CHAT = "general_chat"
BUSINESS = "business"
MEDICINE = "medicine"
MIXED = "mixed"

_GREETING_PATTERNS = (
    "hi", "hii", "hiii", "hello", "hey", "hy", "yo",
    "good morning", "good afternoon", "good evening", "good night",
    "how are you", "what's up", "whats up", "sup",
    "thanks", "thank you", "thx", "ok", "okay", "cool", "nice",
    "who are you", "what can you do", "what is your name",
    "bye", "goodbye", "see you",
)

_BUSINESS_KEYWORDS = (
    "profit", "revenue", "sales", "sale", "stock", "inventory", "expiry",
    "expire", "expiring", "dead stock", "purchase", "order", "reorder",
    "supplier", "distributor", "forecast", "demand", "low stock",
    "health score", "loss", "leak", "margin", "cost", "price", "today",
    "this month", "last month", "this week", "opportunity", "purchase plan",
)

_MEDICINE_KEYWORDS = (
    "schedule h", "compliance", "prescription", "dosage", "dose", "sop",
    "regulation", "regulatory", "license", "gst", "hsn", "expiry disposal",
    "antibiotic", "drug information", "side effect", "interaction",
    "storage condition", "shelf life", "policy", "guideline",
)


def classify(message: str) -> str:
    normalized = message.strip().lower().strip("!?. ")
    if not normalized:
        return GENERAL_CHAT

    # Greeting check first — but only for short messages, so a real
    # question that happens to start with "hi" doesn't get misclassified.
    if normalized in _GREETING_PATTERNS:
        return GREETING
    if len(normalized.split()) <= 4:
        for p in _GREETING_PATTERNS:
            if normalized.startswith(p):
                return GREETING

    has_business = any(kw in normalized for kw in _BUSINESS_KEYWORDS)
    has_medicine = any(kw in normalized for kw in _MEDICINE_KEYWORDS)

    if has_business and has_medicine:
        return MIXED
    if has_medicine:
        return MEDICINE
    if has_business:
        return BUSINESS

    # No clear business/medicine keywords and not a greeting — treat as
    # general conversation (e.g. "what's the weather like", "tell me a joke").
    return GENERAL_CHAT


_VISUALIZE_KEYWORDS = (
    "chart", "graph", "visuali", "plot", "table", "show me a", "draw",
    "compare", "trend", "breakdown", "dashboard", "report",
    "card", "figure", "insight", "over time", "by month", "by week",
)


def wants_visualization(message: str) -> bool:
    """Detects whether the owner wants a visual artifact (chart/table/cards)
    rather than a text answer. Independent of the 5-way conversational
    intent above — a BUSINESS question can also want a chart. Deliberately
    keyword-based (not a separate LLM call) to keep this cheap to check on
    every message; the actual chart *content* generation is still handled
    by a real LLM call in tool_executor when this returns True."""
    normalized = message.strip().lower()
    if not normalized:
        return False
    return any(kw in normalized for kw in _VISUALIZE_KEYWORDS)
