from flask import Blueprint, jsonify, request
from app.services import memory, conversation_manager

chat_bp = Blueprint("chat", __name__)

DEFAULT_SESSION = "default"


@chat_bp.route("/api/chat/history")
def history():
    session_id = request.args.get("session_id", DEFAULT_SESSION)
    return jsonify(memory.full_history(session_id))


@chat_bp.route("/api/chat/message", methods=["POST"])
def send_message():
    data = request.get_json(force=True) or {}
    user_text = (data.get("message") or "").strip()
    session_id = data.get("session_id", DEFAULT_SESSION)

    if not user_text:
        return jsonify({"error": "message is required"}), 400

    try:
        # conversation_manager owns the full pipeline: memory load -> intent
        # -> context build -> LLM call -> memory save. It saves both turns
        # itself, so the route does not touch ChatMessage directly.
        result = conversation_manager.ask_aloksaar(user_text, session_id=session_id)
    except RuntimeError as e:
        # No API key configured — return a clear error instead of a fake answer
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"AI request failed: {e}"}), 502

    # Return the just-saved pair from history (last 2 entries) so the
    # frontend contract (user_message / assistant_message shape) stays the
    # same as before.
    recent = memory.full_history(session_id)
    user_message = recent[-2] if len(recent) >= 2 else {"role": "user", "content": user_text}
    assistant_message = recent[-1] if recent else {"role": "assistant", "content": result["response"]}

    return jsonify({
        "user_message": user_message,
        "assistant_message": assistant_message,
        "intent": result.get("intent"),
        "offer_visualization": result.get("offer_visualization", False),
    })
