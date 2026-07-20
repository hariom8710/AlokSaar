"""
Business analytics engine for AlokSaar.

This module implements the real (non-LLM) number-crunching that powers the
dashboard and feeds context to the AI assistant: Business Health Score,
Profit Leak Detection, Dead Stock Recovery, Expiry Risk, and Inventory
Optimization signals. The LLM never invents these numbers — it reasons
over them.
"""
from datetime import datetime, date, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models import Medicine, StockBatch, Sale, Purchase, StockOutEvent

EXPIRY_WARNING_DAYS = 90  # items expiring within this window are "at risk"
DEAD_STOCK_DAYS = 60      # no sales in this many days => dead stock candidate
LOW_STOCK_MULTIPLIER = 1.0  # stock <= reorder_level => low stock


def _period_start(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


def todays_snapshot():
    """Revenue, profit, orders, low stock, expiring items, dead stock value, etc.
    Mirrors the 'Today's Snapshot' panel on the AlokSaar dashboard."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    sales_today = Sale.query.filter(Sale.sale_date >= today_start).all()

    revenue = sum(s.revenue for s in sales_today)
    profit = sum(s.profit for s in sales_today)
    orders = len(sales_today)

    # Compare to yesterday for % change
    yesterday_start = today_start - timedelta(days=1)
    sales_yesterday = Sale.query.filter(
        Sale.sale_date >= yesterday_start, Sale.sale_date < today_start
    ).all()
    revenue_y = sum(s.revenue for s in sales_yesterday) or 1
    profit_y = sum(s.profit for s in sales_yesterday) or 1

    revenue_change = round(((revenue - revenue_y) / revenue_y) * 100, 1)
    profit_change = round(((profit - profit_y) / profit_y) * 100, 1)

    expiring_items = expiry_risk_items()
    low_stock = low_stock_items()
    dead_stock = dead_stock_items()
    stock_out = active_stock_outs()

    dead_stock_value = sum(d["value"] for d in dead_stock)
    opportunity_value = round(profit_leak_total() + dead_stock_value * 0.3, 2)

    return {
        "revenue": round(revenue, 2),
        "revenue_change_pct": revenue_change,
        "profit": round(profit, 2),
        "profit_change_pct": profit_change,
        "orders": orders,
        "expiring_items_count": len(expiring_items),
        "low_stock_count": len(low_stock),
        "dead_stock_value": round(dead_stock_value, 2),
        "stock_out_count": len(stock_out),
        "opportunity_value": round(opportunity_value, 2),
    }


def business_health_score():
    """Composite 0-100 score, like the poster's gauge (Profitability, Inventory,
    Sales Trend, Expiry Risk, Stock Availability)."""
    medicines = Medicine.query.all()
    if not medicines:
        return {"score": 0, "label": "No Data", "components": {}}

    total_stock_positions = len(medicines)

    # Profitability: recent 30-day margin %
    recent_sales = Sale.query.filter(Sale.sale_date >= _period_start(30)).all()
    revenue = sum(s.revenue for s in recent_sales) or 1
    profit = sum(s.profit for s in recent_sales)
    margin_pct = max(0, min(100, (profit / revenue) * 100))
    profitability_score = min(100, margin_pct * 4)  # 25% margin -> 100 pts

    # Inventory: % of medicines within healthy stock band (not low, not excess)
    healthy = 0
    for m in medicines:
        stock = m.current_stock
        if m.reorder_level <= stock <= m.ideal_stock_level * 1.5:
            healthy += 1
    inventory_score = (healthy / total_stock_positions) * 100

    # Sales trend: this week vs last week revenue
    this_week = sum(s.revenue for s in Sale.query.filter(Sale.sale_date >= _period_start(7)).all())
    last_week = sum(
        s.revenue for s in Sale.query.filter(
            Sale.sale_date >= _period_start(14), Sale.sale_date < _period_start(7)
        ).all()
    ) or 1
    trend_ratio = this_week / last_week
    sales_trend_score = max(0, min(100, trend_ratio * 70))  # flat growth ~70

    # Expiry risk: fewer near-expiry batches (by value) = better
    at_risk_value = sum(i["value"] for i in expiry_risk_items())
    total_inventory_value = sum(
        float(m.unit_cost or 0) * m.current_stock for m in medicines
    ) or 1
    expiry_ratio = at_risk_value / total_inventory_value
    expiry_score = max(0, 100 - (expiry_ratio * 300))

    # Stock availability: % of medicines currently above 0 stock
    in_stock = sum(1 for m in medicines if m.current_stock > 0)
    availability_score = (in_stock / total_stock_positions) * 100

    components = {
        "profitability": round(profitability_score, 1),
        "inventory": round(inventory_score, 1),
        "sales_trend": round(sales_trend_score, 1),
        "expiry_risk": round(expiry_score, 1),
        "stock_availability": round(availability_score, 1),
    }
    overall = round(sum(components.values()) / len(components))

    if overall >= 80:
        label = "Good"
    elif overall >= 60:
        label = "Fair"
    else:
        label = "Needs Attention"

    return {"score": overall, "label": label, "components": components}


def expiry_risk_items(within_days: int = EXPIRY_WARNING_DAYS):
    """Batches expiring soon, with estimated value at risk."""
    cutoff = date.today() + timedelta(days=within_days)
    batches = StockBatch.query.filter(
        StockBatch.expiry_date <= cutoff, StockBatch.quantity > 0
    ).all()
    results = []
    for b in batches:
        med = b.medicine
        value = float(med.unit_cost or 0) * b.quantity
        results.append({
            "medicine_id": med.id,
            "medicine_name": med.name,
            "batch_number": b.batch_number,
            "quantity": b.quantity,
            "expiry_date": b.expiry_date.isoformat(),
            "days_to_expiry": b.days_to_expiry(),
            "value": round(value, 2),
        })
    return sorted(results, key=lambda x: x["days_to_expiry"])


def dead_stock_items(days: int = DEAD_STOCK_DAYS):
    """Medicines with stock on hand but no sales in the given window."""
    cutoff = _period_start(days)
    medicines = Medicine.query.all()
    results = []
    for m in medicines:
        if m.current_stock <= 0:
            continue
        recent_sale = Sale.query.filter(
            Sale.medicine_id == m.id, Sale.sale_date >= cutoff
        ).first()
        if recent_sale is None:
            value = float(m.unit_cost or 0) * m.current_stock
            results.append({
                "medicine_id": m.id,
                "medicine_name": m.name,
                "current_stock": m.current_stock,
                "value": round(value, 2),
            })
    return sorted(results, key=lambda x: -x["value"])


def low_stock_items():
    medicines = Medicine.query.all()
    return [
        {
            "medicine_id": m.id,
            "medicine_name": m.name,
            "current_stock": m.current_stock,
            "reorder_level": m.reorder_level,
        }
        for m in medicines
        if 0 < m.current_stock <= m.reorder_level * LOW_STOCK_MULTIPLIER
    ]


def active_stock_outs():
    events = StockOutEvent.query.filter(StockOutEvent.end_date.is_(None)).all()
    return [e.to_dict() for e in events]


def sales_trend_series(days: int = 14):
    """Daily revenue & profit for the last N days — powers the dashboard trend chart."""
    end_date = date.today()
    start_date = end_date - timedelta(days=max(1, days) - 1)
    return sales_trend_series_between(start_date, end_date)


def sales_trend_series_between(start_date: date, end_date: date):
    """Daily revenue and profit for an inclusive user-selected date range."""
    if end_date < start_date:
        raise ValueError("End date must be on or after start date")

    since = datetime.combine(start_date, datetime.min.time())
    until = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    sales = Sale.query.filter(Sale.sale_date >= since, Sale.sale_date < until).all()

    buckets = {}
    day_count = (end_date - start_date).days + 1
    for i in range(day_count):
        d = (start_date + timedelta(days=i)).isoformat()
        buckets[d] = {"revenue": 0.0, "profit": 0.0}

    for s in sales:
        d = s.sale_date.date().isoformat()
        if d in buckets:
            buckets[d]["revenue"] += s.revenue
            buckets[d]["profit"] += s.profit

    labels = list(buckets.keys())
    return {
        "labels": labels,
        "revenue": [round(buckets[d]["revenue"], 2) for d in labels],
        "profit": [round(buckets[d]["profit"], 2) for d in labels],
    }


def profit_leak_total():
    """Sum of estimated losses: expired-stock write-offs implied by near-expiry value
    plus lost sales from active stock-outs. Used for the 'Opportunities' figure."""
    expiry_loss = sum(i["value"] for i in expiry_risk_items(within_days=15))  # imminent
    stock_out_loss = sum(float(e.estimated_lost_sales or 0) for e in StockOutEvent.query.all())
    return round(expiry_loss + stock_out_loss, 2)


def profit_leak_report():
    """Detailed breakdown for the 'AI Profit Leak Detector' feature — the kind of
    answer shown in the poster's example conversation."""
    imminent_expiry = expiry_risk_items(within_days=15)
    stock_outs = StockOutEvent.query.all()
    dead_stock = dead_stock_items()

    reasons = []
    total_loss = 0.0

    if imminent_expiry:
        loss = sum(i["value"] for i in imminent_expiry)
        total_loss += loss
        reasons.append({
            "type": "expiry_loss",
            "description": f"{len(imminent_expiry)} batch(es) expiring within 15 days",
            "estimated_loss": round(loss, 2),
            "items": imminent_expiry[:5],
        })

    for e in stock_outs:
        if e.estimated_lost_sales:
            total_loss += float(e.estimated_lost_sales)
            days_out = ((e.end_date or date.today()) - e.start_date).days
            reasons.append({
                "type": "stock_out_loss",
                "description": f"{e.medicine.name if e.medicine else 'Item'} was out of stock for {days_out} day(s)",
                "estimated_loss": round(float(e.estimated_lost_sales), 2),
            })

    if dead_stock:
        slow_value = sum(d["value"] for d in dead_stock)
        reasons.append({
            "type": "slow_moving_inventory",
            "description": f"{len(dead_stock)} item(s) with no sales in {DEAD_STOCK_DAYS} days",
            "estimated_loss": round(slow_value, 2),
            "items": dead_stock[:5],
        })

    return {
        "total_estimated_loss": round(total_loss, 2),
        "reasons": reasons,
    }


def inventory_optimizer_suggestions():
    """Recommends what to restock, reduce, or return — feeds Purchase Advisor / Copilot."""
    suggestions = []
    for item in low_stock_items():
        suggestions.append({
            "type": "restock",
            "medicine_name": item["medicine_name"],
            "message": f"Stock is low ({item['current_stock']} left, reorder level {item['reorder_level']}). Consider restocking soon.",
        })
    for item in dead_stock_items()[:5]:
        suggestions.append({
            "type": "reduce",
            "medicine_name": item["medicine_name"],
            "message": f"No sales recently, {item['current_stock']} units worth ₹{item['value']:.0f} tied up. Consider a discount or return.",
        })
def full_dashboard_payload():
    from app.services import forecasting

    print("STEP 1: Snapshot")
    snapshot = todays_snapshot()

    print("STEP 2: Health Score")
    health = business_health_score()

    print("STEP 3: Expiry")
    expiry = expiry_risk_items(within_days=60)

    print("STEP 4: Low Stock")
    low_stock = low_stock_items()

    print("STEP 5: Dead Stock")
    dead_stock = dead_stock_items()

    print("STEP 6: Profit Leak")
    profit_leak = profit_leak_report()

    print("STEP 7: Purchase Plan")
    purchase_plan = forecasting.next_week_purchase_plan()

    print("STEP 8: Sales Trend")
    sales_trend = sales_trend_series(days=14)

    print("DONE")

    return {
        "snapshot": snapshot,
        "health_score": health,
        "expiry_at_risk": expiry,
        "low_stock": low_stock,
        "dead_stock": dead_stock,
        "profit_leak": profit_leak,
        "purchase_plan": purchase_plan,
        "sales_trend": sales_trend,
    }
