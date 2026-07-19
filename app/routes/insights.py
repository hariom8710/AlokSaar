import re
from datetime import date
from flask import Blueprint, jsonify, render_template, request
from app.services import memory, conversation_manager, visualization_builder

insights_bp = Blueprint("insights", __name__)

INSIGHTS_SESSION_PREFIX = "insights_"


def _resolve_visualization_range():
    """Accept preset days, typed durations (e.g. '1 month'), or ISO dates."""
    start_raw = request.args.get("start", "").strip()
    end_raw = request.args.get("end", "").strip()
    if start_raw or end_raw:
        if not (start_raw and end_raw):
            raise ValueError("Choose both a start and an end date.")
        start_date = date.fromisoformat(start_raw)
        end_date = date.fromisoformat(end_raw)
        if end_date < start_date:
            raise ValueError("End date must be on or after start date.")
        return (end_date - start_date).days + 1, start_date, end_date

    typed_range = request.args.get("range", "").strip().lower()
    if typed_range:
        match = re.fullmatch(r"(\d+)\s*(day|week|month|year)s?", typed_range)
        if not match:
            raise ValueError("Use a duration like '1 day', '2 weeks', '1 month', or '1 year'.")
        amount, unit = int(match.group(1)), match.group(2)
        days = amount * {"day": 1, "week": 7, "month": 30, "year": 365}[unit]
    else:
        days = request.args.get("days", 14, type=int)
    if not 1 <= days <= 3650:
        raise ValueError("Choose a period between 1 day and 10 years.")
    return days, None, None


def _session_id_for(request_session_id: str) -> str:
    """Insights page uses its own conversation session, separate from the
    main /chat page, so the two don't share or clash history."""
    return f"{INSIGHTS_SESSION_PREFIX}{request_session_id}"


@insights_bp.route("/insights")
def insights_page():
    return render_template("insights.html")


@insights_bp.route("/api/insights/history")
def insights_history():
    session_id = _session_id_for(request.args.get("session_id", "default"))
    return jsonify(memory.full_history(session_id))


@insights_bp.route("/api/insights/message", methods=["POST"])
def insights_message():
    data = request.get_json(force=True) or {}
    user_text = (data.get("message") or "").strip()
    session_id = _session_id_for(data.get("session_id", "default"))

    if not user_text:
        return jsonify({"error": "message is required"}), 400

    try:
        result = conversation_manager.ask_aloksaar(user_text, session_id=session_id)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"AI request failed: {e}"}), 502

    recent = memory.full_history(session_id)
    user_message = recent[-2] if len(recent) >= 2 else {"role": "user", "content": user_text}
    assistant_message = recent[-1] if recent else {"role": "assistant", "content": result["response"]}

    return jsonify({
        "user_message": user_message,
        "assistant_message": assistant_message,
        "intent": result.get("intent"),
    })


@insights_bp.route("/api/insights/visualize", methods=["POST"])
def insights_visualize():
    """Generates the chart/table/card-grid spec for the canvas. Separate
    endpoint from /api/insights/message so the canvas can be refreshed or
    regenerated without re-running the conversational reply."""
    data = request.get_json(force=True) or {}
    user_text = (data.get("message") or "").strip()

    if not user_text:
        return jsonify({"error": "message is required"}), 400

    try:
        days, start_date, end_date = _resolve_visualization_range()
        result = visualization_builder.build_visualization(user_text, days=days, start_date=start_date, end_date=end_date)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Visualization generation failed: {e}"}), 502

    return jsonify(result)
