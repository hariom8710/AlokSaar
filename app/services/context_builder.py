"""
Context Builder — assembles the context block handed to the LLM, shaped by
the intent classification from intent_service.py:

  GREETING / GENERAL_CHAT  — no extra context, keeps replies fast and natural
  BUSINESS                 — live business data only
  MEDICINE                 — RAG knowledge base only
  MIXED                    — both, combined

This mirrors the diagram's "Context Builder (Business + RAG + Memory)" box.
Memory itself is handled separately (it's the message history passed to the
LLM call directly) — this module builds the *extra* context injected into
the current turn's message.
"""
from app.rag.retriever import retrieve
from app.services import analytics, forecasting, planner
from app.services.intent_service import GREETING, GENERAL_CHAT, BUSINESS, MEDICINE, MIXED


def _business_context() -> str:
    snapshot = analytics.todays_snapshot()
    health = analytics.business_health_score()
    leak_report = analytics.profit_leak_report()
    dead_stock = analytics.dead_stock_items()[:5]
    expiring = analytics.expiry_risk_items(within_days=30)[:5]
    low_stock = analytics.low_stock_items()[:5]
    purchase_plan = forecasting.next_week_purchase_plan()[:5]

    lines = ["=== LIVE BUSINESS DATA ==="]
    lines.append(f"Today's snapshot: {snapshot}")
    lines.append(f"Business health score: {health['score']}/100 ({health['label']}); components: {health['components']}")
    lines.append(f"Profit leak report: total estimated loss ₹{leak_report['total_estimated_loss']}")
    for r in leak_report["reasons"]:
        lines.append(f"  - {r['description']}: ₹{r['estimated_loss']}")
    if dead_stock:
        lines.append("Dead stock (no recent sales): " + "; ".join(
            f"{d['medicine_name']} ({d['current_stock']} units, ₹{d['value']})" for d in dead_stock
        ))
    if expiring:
        lines.append("Expiring within 30 days: " + "; ".join(
            f"{e['medicine_name']} ({e['quantity']} units, {e['days_to_expiry']} days left)" for e in expiring
        ))
    if low_stock:
        lines.append("Low stock items: " + "; ".join(
            f"{l['medicine_name']} ({l['current_stock']} left, reorder at {l['reorder_level']})" for l in low_stock
        ))
    if purchase_plan:
        lines.append("Recommended next-week purchase plan: " + "; ".join(
            f"{p['medicine_name']} — order ~{p['recommended_order_qty']} units (forecast demand {p['forecast_units']})"
            for p in purchase_plan
        ))

    lines.append("")
    lines.append("=== PRIORITIZED RECOMMENDATIONS (pre-computed, highest impact first) ===")
    lines.append(planner.recommendations_summary_text(limit=5))

    return "\n".join(lines)


def _rag_context(query: str) -> str:
    try:
        hits = retrieve(query, n_results=3)
    except Exception:
        return ""
    if not hits:
        return ""
    lines = ["=== KNOWLEDGE BASE (RAG) ==="]
    for h in hits:
        lines.append(f"[{h['category']}] {h['text']}")
    return "\n".join(lines)


def build(intent: str, user_message: str) -> str:
    """Returns the extra context block to prepend to the user's message,
    shaped by intent. Empty string for greeting/general chat — deliberately,
    so casual replies aren't forced to reference business data."""
    if intent in (GREETING, GENERAL_CHAT):
        return ""

    if intent == BUSINESS:
        return _business_context()

    if intent == MEDICINE:
        return _rag_context(user_message)

    if intent == MIXED:
        business = _business_context()
        rag = _rag_context(user_message)
        return f"{business}\n\n{rag}" if rag else business

    return ""
