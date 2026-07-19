"""
AI Demand Forecasting service.

Uses a lightweight trend + moving-average model over historical sales to
predict next-period demand per medicine. This is intentionally simple and
dependency-light (pandas/numpy only) so it runs without training a heavy
model — swap in Prophet/ARIMA here for production-grade forecasting; the
interface (forecast_demand) would stay the same.
"""
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from app.models import Sale, Medicine


def _sales_dataframe(medicine_id: int, days: int = 60) -> pd.DataFrame:
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        Sale.query.filter(Sale.medicine_id == medicine_id, Sale.sale_date >= since)
        .order_by(Sale.sale_date.asc())
        .all()
    )
    if not rows:
        return pd.DataFrame(columns=["date", "quantity"])
    df = pd.DataFrame([{"date": r.sale_date.date(), "quantity": r.quantity} for r in rows])
    daily = df.groupby("date")["quantity"].sum().reset_index()
    return daily


def forecast_demand(medicine_id: int, horizon_days: int = 7) -> dict:
    """Forecast total units likely needed over the next `horizon_days`."""
    medicine = Medicine.query.get(medicine_id)
    if medicine is None:
        return {"error": "medicine not found"}

    daily = _sales_dataframe(medicine_id)
    if daily.empty or len(daily) < 3:
        # Not enough history — fall back to a conservative estimate based on reorder level
        baseline = max(1, medicine.reorder_level // 4)
        return {
            "medicine_id": medicine_id,
            "medicine_name": medicine.name,
            "method": "baseline_fallback",
            "avg_daily_demand": baseline,
            "forecast_units": baseline * horizon_days,
            "current_stock": medicine.current_stock,
            "days_of_stock_remaining": round(medicine.current_stock / baseline, 1) if baseline else None,
            "recommended_order_qty": max(0, (baseline * horizon_days) - medicine.current_stock),
        }

    quantities = daily["quantity"].values.astype(float)

    # Simple weighted trend: recent days count more (like exponential smoothing)
    weights = np.linspace(1, 2, num=len(quantities))
    weighted_avg = float(np.average(quantities, weights=weights))

    # Trend slope via linear regression over the recent window
    x = np.arange(len(quantities))
    if len(quantities) >= 2:
        slope = float(np.polyfit(x, quantities, 1)[0])
    else:
        slope = 0.0

    projected_daily = max(0.0, weighted_avg + slope * (horizon_days / 2))
    forecast_units = round(projected_daily * horizon_days)

    days_of_stock = round(medicine.current_stock / projected_daily, 1) if projected_daily > 0 else None
    recommended_qty = max(0, forecast_units - medicine.current_stock + medicine.reorder_level)

    return {
        "medicine_id": medicine_id,
        "medicine_name": medicine.name,
        "method": "weighted_trend",
        "avg_daily_demand": round(projected_daily, 1),
        "forecast_units": int(forecast_units),
        "current_stock": medicine.current_stock,
        "days_of_stock_remaining": days_of_stock,
        "recommended_order_qty": int(recommended_qty),
    }


def forecast_all(horizon_days: int = 7) -> list:
    medicines = Medicine.query.all()
    return [forecast_demand(m.id, horizon_days) for m in medicines]


def next_week_purchase_plan() -> list:
    """Purchase Advisor: which medicines to order and how much, ranked by urgency."""
    forecasts = forecast_all(horizon_days=7)
    plan = [f for f in forecasts if f.get("recommended_order_qty", 0) > 0]
    plan.sort(key=lambda f: f.get("days_of_stock_remaining") or 999)
    return plan
