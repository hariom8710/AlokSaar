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
    medicine_counts = (
        db.session.query(
            Medicine.supplier_id,
            func.count(Medicine.id).label("medicine_count"),
        )
        .filter(Medicine.supplier_id.isnot(None))
        .group_by(Medicine.supplier_id)
        .subquery()
    )
    purchase_stats = (
        db.session.query(
            Purchase.supplier_id,
            func.count(Purchase.id).label("order_count"),
            func.avg(Purchase.unit_cost).label("avg_unit_cost"),
            func.sum(Purchase.quantity * Purchase.unit_cost).label("total_spend"),
        )
        .filter(Purchase.supplier_id.isnot(None))
        .group_by(Purchase.supplier_id)
        .subquery()
    )
    rows = (
        db.session.query(
            Supplier,
            func.coalesce(medicine_counts.c.medicine_count, 0),
            func.coalesce(purchase_stats.c.order_count, 0),
            purchase_stats.c.avg_unit_cost,
            func.coalesce(purchase_stats.c.total_spend, 0),
        )
        .outerjoin(medicine_counts, medicine_counts.c.supplier_id == Supplier.id)
        .outerjoin(purchase_stats, purchase_stats.c.supplier_id == Supplier.id)
        .order_by(Supplier.name)
        .all()
    )
    result = []
    for s, medicine_count, order_count, avg_unit_cost, total_spend in rows:
        result.append({
            **s.to_dict(),
            "medicine_count": medicine_count,
            "order_count": order_count or 0,
            "avg_unit_cost": round(float(avg_unit_cost), 2) if avg_unit_cost else None,
            "total_spend": round(float(total_spend), 2) if total_spend else 0,
        })
    return jsonify(result)
