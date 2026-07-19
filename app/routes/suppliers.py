from flask import Blueprint, jsonify, render_template
from app.models import Supplier, Medicine, Purchase
from app.extensions import db
from sqlalchemy import func

suppliers_bp = Blueprint("suppliers", __name__)


@suppliers_bp.route("/suppliers")
def suppliers_page():
    return render_template("suppliers.html")


@suppliers_bp.route("/api/suppliers")
def list_suppliers():
    suppliers = Supplier.query.all()
    result = []
    for s in suppliers:
        medicine_count = Medicine.query.filter_by(supplier_id=s.id).count()
        purchase_stats = (
            db.session.query(
                func.count(Purchase.id),
                func.avg(Purchase.unit_cost),
                func.sum(Purchase.quantity * Purchase.unit_cost),
            )
            .filter(Purchase.supplier_id == s.id)
            .first()
        )
        order_count, avg_unit_cost, total_spend = purchase_stats
        result.append({
            **s.to_dict(),
            "medicine_count": medicine_count,
            "order_count": order_count or 0,
            "avg_unit_cost": round(float(avg_unit_cost), 2) if avg_unit_cost else None,
            "total_spend": round(float(total_spend), 2) if total_spend else 0,
        })
    return jsonify(result)
