from flask import Blueprint, jsonify, request
from app.services import forecasting

purchase_bp = Blueprint("purchase", __name__)


@purchase_bp.route("/api/demand/forecast/<int:medicine_id>")
def forecast_one(medicine_id):
    horizon = request.args.get("horizon_days", 7, type=int)
    return jsonify(forecasting.forecast_demand(medicine_id, horizon_days=horizon))


@purchase_bp.route("/api/demand/forecast-all")
def forecast_all():
    horizon = request.args.get("horizon_days", 7, type=int)
    return jsonify(forecasting.forecast_all(horizon_days=horizon))


@purchase_bp.route("/api/purchase/next-week-plan")
def next_week_plan():
    return jsonify(forecasting.next_week_purchase_plan())
