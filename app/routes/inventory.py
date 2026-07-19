from flask import Blueprint, jsonify, request
from app.models import Medicine
from app.services import analytics

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/api/inventory")
def list_inventory():
    medicines = Medicine.query.all()
    return jsonify([m.to_dict() for m in medicines])


@inventory_bp.route("/api/inventory/low-stock")
def low_stock():
    return jsonify(analytics.low_stock_items())


@inventory_bp.route("/api/inventory/dead-stock")
def dead_stock():
    days = request.args.get("days", 60, type=int)
    return jsonify(analytics.dead_stock_items(days=days))


@inventory_bp.route("/api/inventory/optimizer-suggestions")
def optimizer_suggestions():
    return jsonify(analytics.inventory_optimizer_suggestions())


@inventory_bp.route("/api/expiry/at-risk")
def expiry_at_risk():
    days = request.args.get("days", 90, type=int)
    return jsonify(analytics.expiry_risk_items(within_days=days))
