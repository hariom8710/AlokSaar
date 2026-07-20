from flask import Blueprint, jsonify, render_template, request
from app.services import analytics

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    return render_template("dashboard.html")


@dashboard_bp.route("/chat")
def chat_page():
    return render_template("chat.html")


@dashboard_bp.route("/api/dashboard/snapshot")
def snapshot():
    return jsonify(analytics.todays_snapshot())


@dashboard_bp.route("/api/dashboard/health-score")
def health_score():
    return jsonify(analytics.business_health_score())


@dashboard_bp.route("/api/dashboard/profit-leak")
def profit_leak():
    return jsonify(analytics.profit_leak_report())


@dashboard_bp.route("/api/dashboard/sales-trend")
def sales_trend():
    days = request.args.get("days", 14, type=int)
    return jsonify(analytics.sales_trend_series(days=days))

@dashboard_bp.route("/api/dashboard/all")
def dashboard_all():
    try:
        return jsonify(analytics.full_dashboard_payload())
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e)
        }), 500