"""
Visualization Builder — generates a structured "canvas spec" (chart, table,
or card-grid blocks) for the Insights page, grounded in real business data.

This is a SEPARATE, focused LLM call from the normal conversational reply —
asked only when intent_service.wants_visualization() is True. Keeping it
separate means:
  - The main chat reply stays fast for every other message (no extra call).
  - This call's prompt can demand strict JSON output without fighting the
    main system prompt's conversational/Markdown formatting rules.
  - The output is validated against a fixed schema before being trusted,
    since a malformed block would break the frontend renderer.

Supported block types (v1): "chart" (line/bar), "table", "card_grid".
"""
import json
import re
from app.services import analytics, forecasting, tool_executor

_ALLOWED_BLOCK_TYPES = {"chart", "table", "card_grid"}
_ALLOWED_CHART_TYPES = {"line", "bar"}

VIZ_SYSTEM_PROMPT = """You generate structured visualization specs for a \
pharmacy business dashboard. You are given real business data. Your job is \
to decide which chart(s), table(s), or summary card(s) best answer the \
owner's request, and output ONLY valid JSON — no prose, no markdown fences, \
no explanation before or after.

Output schema (a JSON object with a "blocks" array; each block is ONE of):

Chart block:
{"type": "chart", "chart_type": "line" | "bar", "title": "string",
 "labels": ["string", ...], "series": [{"name": "string", "data": [number, ...]}]}

Table block:
{"type": "table", "title": "string", "columns": ["string", ...],
 "rows": [["cell", "cell", ...], ...]}

Card grid block:
{"type": "card_grid", "title": "string",
 "cards": [{"label": "string", "value": "string", "trend": "up" | "down" | "neutral"}]}

Rules:
- Keep every "title" SHORT — 3-6 words max (e.g. "Revenue Trend", not "14-Day Sales Trend Showing Revenue and Profit Over Time").
- Keep chart labels SHORT — use short date/day formats (e.g. "Jul 14", not full sentences).
- Be economical with the JSON itself: no extra whitespace, no repeated fields. Output the most compact valid JSON that fits the schema.
- Use ONLY the numbers present in the provided business data — never invent figures.
- Prefer 1-2 blocks total unless the request clearly needs more.
- Choose the block type that best fits: trends over time -> chart; \
comparing several items with multiple attributes -> table; a handful of \
headline numbers -> card_grid.
- If the data needed isn't available in what you were given, output an \
empty blocks array: {"blocks": []}
- Output raw JSON only. Do not wrap it in ```json or any other text.
"""


def _gather_visualization_data(days: int = 14, start_date=None, end_date=None) -> str:
    """Same live business data as the main context builder — kept
    independent so this module has no import dependency on
    context_builder.py, avoiding any circular-import risk."""
    snapshot = analytics.todays_snapshot()
    health = analytics.business_health_score()
    trend = analytics.sales_trend_series_between(start_date, end_date) if start_date and end_date else analytics.sales_trend_series(days=days)
    expiring = analytics.expiry_risk_items(within_days=30)
    low_stock = analytics.low_stock_items()
    dead_stock = analytics.dead_stock_items()
    purchase_plan = forecasting.next_week_purchase_plan()

    lines = ["=== BUSINESS DATA FOR VISUALIZATION ==="]
    lines.append(f"Today's snapshot: {snapshot}")
    lines.append(f"Health score: {health['score']}/100; components: {health['components']}")
    lines.append(f"{days}-day sales trend: labels={trend['labels']}, revenue={trend['revenue']}, profit={trend['profit']}")
    lines.append(f"Expiring within 30 days: {expiring}")
    lines.append(f"Low stock items: {low_stock}")
    lines.append(f"Dead stock items: {dead_stock}")
    lines.append(f"Next week purchase plan: {purchase_plan}")
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """Extracts and parses the JSON object from the LLM's response, robust
    to real-world LLM behavior: leading/trailing prose ("Sure! Here's the
    chart:"), markdown code fences anywhere in the text, or a mix of both.
    Tries progressively looser strategies rather than assuming the response
    is pure JSON with fences exactly at the start and end."""
    cleaned = text.strip()

    # Strategy 1: response is pure JSON already (fast path, no regex needed)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find a ```json ... ``` or ``` ... ``` fenced block anywhere
    # in the text, not just at the exact start/end of the string.
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: no fences, but there's prose around a raw JSON object —
    # grab from the first '{' to the last '}' in the whole response.
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # All strategies failed — raise so the caller's except block handles it
    # and returns a clean empty-blocks response instead of crashing.
    raise ValueError(f"Could not extract valid JSON from LLM response: {cleaned[:200]!r}")


def _validate_block(block: dict) -> bool:
    if not isinstance(block, dict):
        return False
    btype = block.get("type")
    if btype not in _ALLOWED_BLOCK_TYPES:
        return False
    if btype == "chart":
        if block.get("chart_type") not in _ALLOWED_CHART_TYPES:
            return False
        if not isinstance(block.get("labels"), list) or not isinstance(block.get("series"), list):
            return False
        if not block["labels"] or not block["series"]:
            return False
        for series in block["series"]:
            if not isinstance(series, dict) or not isinstance(series.get("data"), list):
                return False
            if len(series["data"]) != len(block["labels"]) or not all(isinstance(value, (int, float)) for value in series["data"]):
                return False
    elif btype == "table":
        if not isinstance(block.get("columns"), list) or not isinstance(block.get("rows"), list):
            return False
        if any(not isinstance(row, list) or len(row) != len(block["columns"]) for row in block["rows"]):
            return False
    elif btype == "card_grid":
        if not isinstance(block.get("cards"), list) or not all(isinstance(card, dict) for card in block["cards"]):
            return False
    return True


def _deterministic_visualization(user_message: str, days: int, start_date=None, end_date=None) -> dict:
    """Build a useful canvas from live data even when the AI provider is down.
    This keeps Insights usable and ensures every displayed value is sourced
    directly from the database."""
    text = user_message.lower()
    trend = analytics.sales_trend_series_between(start_date, end_date) if start_date and end_date else analytics.sales_trend_series(days=days)
    snapshot = analytics.todays_snapshot()
    blocks = [{
        "type": "card_grid", "title": "Business Snapshot", "cards": [
            {"label": "Revenue today", "value": f"₹{snapshot['revenue']:,.0f}", "trend": "up" if snapshot["revenue_change_pct"] >= 0 else "down"},
            {"label": "Profit today", "value": f"₹{snapshot['profit']:,.0f}", "trend": "up" if snapshot["profit_change_pct"] >= 0 else "down"},
            {"label": "Orders today", "value": str(snapshot["orders"]), "trend": "neutral"},
            {"label": "Low-stock items", "value": str(snapshot["low_stock_count"]), "trend": "down" if snapshot["low_stock_count"] else "neutral"},
        ]
    }]

    if any(word in text for word in ("low stock", "inventory", "purchase", "restock")):
        rows = analytics.low_stock_items()
        blocks.append({"type": "table", "title": "Low Stock Items", "columns": ["Medicine", "In stock", "Reorder level"],
                       "rows": [[item["medicine_name"], item["current_stock"], item["reorder_level"]] for item in rows]})
    elif any(word in text for word in ("expiry", "expiring", "expire")):
        rows = analytics.expiry_risk_items(within_days=90)
        blocks.append({"type": "table", "title": "Expiry Risk", "columns": ["Medicine", "Batch", "Days left", "Units"],
                       "rows": [[item["medicine_name"], item["batch_number"] or "—", item["days_to_expiry"], item["quantity"]] for item in rows]})
    else:
        series = [{"name": "Revenue", "data": trend["revenue"]}]
        if any(word in text for word in ("profit", "sales", "trend", "compare", "dashboard", "report")):
            series.append({"name": "Profit", "data": trend["profit"]})
        blocks.append({"type": "chart", "chart_type": "bar" if "bar" in text else "line",
                       "title": f"Sales Trend ({days} Days)", "labels": trend["labels"], "series": series})
    return {"blocks": blocks, "source": "live_data"}


def build_visualization(user_message: str, days: int = 14, start_date=None, end_date=None) -> dict:
    """Returns {"blocks": [...]} — validated, ready for the frontend.
    Falls back to an empty block list (never raises) if the LLM output is
    malformed, so a visualization failure never breaks the chat response
    itself — the panel would just show 'nothing to display' rather than
    crash the page."""
    days = max(1, min(int(days), 365))
    data_context = _gather_visualization_data(days, start_date, end_date)
    messages = [{
        "role": "user",
        "content": f"{data_context}\n\n=== OWNER'S REQUEST ===\n{user_message}",
    }]

    try:
        raw = tool_executor.generate_response(
    VIZ_SYSTEM_PROMPT, messages, max_tokens=tool_executor.VISUALIZATION_MAX_TOKENS
)
        parsed = _extract_json(raw)
        blocks = parsed.get("blocks", [])
        valid_blocks = [b for b in blocks if _validate_block(b)]
        if not valid_blocks and blocks:
            print(f"[AlokSaar] Visualization: {len(blocks)} block(s) returned but none were valid: {blocks}")
        if valid_blocks:
            return {"blocks": valid_blocks, "source": "ai"}
        return _deterministic_visualization(user_message, days, start_date, end_date)
    except Exception as e:
        print(f"[AlokSaar] Visualization generation failed for request '{user_message}': {e}")
        fallback = _deterministic_visualization(user_message, days, start_date, end_date)
        fallback["warning"] = "AI visualization was unavailable, so this canvas was built from live business data."
        return fallback
