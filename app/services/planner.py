"""
Planner — turns raw business analytics into a short list of structured,
prioritized recommendations. This is the "Recommendation Engine" referenced
in the project spec: purchase planning, expiry management, dead stock
recovery, and cost reduction, distilled into actionable next steps.

Used by context_builder.py to give the LLM a pre-digested action list for
BUSINESS/MIXED intents, rather than making the model infer priorities from
raw numbers alone — improves consistency of the "2-3 action items" the
system prompt asks for.
"""
from app.services import analytics, forecasting


def build_recommendations(limit: int = 5) -> list:
    """Returns a prioritized list of {priority, type, message} recommendations,
    highest-impact first (by estimated rupee value where available)."""
    recs = []

    # Expiry — highest urgency first (compliance/legal risk)
    for item in analytics.expiry_risk_items(within_days=15):
        recs.append({
            "priority": 1,
            "type": "expiry",
            "value": item["value"],
            "message": (
                f"{item['medicine_name']}: {item['quantity']} units expire in "
                f"{item['days_to_expiry']} days (₹{item['value']:.0f}). Pull from shelf, "
                f"attempt distributor return, or discount immediately."
            ),
        })

    # Stock-outs — lost sales, second priority
    for item in analytics.active_stock_outs():
        recs.append({
            "priority": 2,
            "type": "stock_out",
            "value": item["estimated_lost_sales"],
            "message": (
                f"{item['medicine_name']} is currently out of stock "
                f"(est. ₹{item['estimated_lost_sales']:.0f} lost sales). Reorder urgently."
            ),
        })

    # Low stock — proactive reorder
    for item in analytics.low_stock_items():
        recs.append({
            "priority": 3,
            "type": "low_stock",
            "value": 0,
            "message": (
                f"{item['medicine_name']}: {item['current_stock']} left "
                f"(reorder level {item['reorder_level']}). Reorder soon to avoid a stock-out."
            ),
        })

    # Dead stock — capital recovery
    for item in analytics.dead_stock_items()[:5]:
        recs.append({
            "priority": 4,
            "type": "dead_stock",
            "value": item["value"],
            "message": (
                f"{item['medicine_name']}: {item['current_stock']} units "
                f"(₹{item['value']:.0f}) with no recent sales. Consider a discount or "
                f"return; stop reordering this SKU in bulk."
            ),
        })

    # Purchase plan — proactive demand-driven ordering
    for item in forecasting.next_week_purchase_plan()[:3]:
        recs.append({
            "priority": 5,
            "type": "purchase",
            "value": 0,
            "message": (
                f"Order ~{item['recommended_order_qty']} units of {item['medicine_name']} "
                f"this week based on demand forecast."
            ),
        })

    recs.sort(key=lambda r: (r["priority"], -r["value"]))
    return recs[:limit]


def recommendations_summary_text(limit: int = 5) -> str:
    """Flattened text form for injecting into LLM context."""
    recs = build_recommendations(limit=limit)
    if not recs:
        return "No urgent recommendations right now — business looks healthy."
    return "\n".join(f"{i+1}. {r['message']}" for i, r in enumerate(recs))
