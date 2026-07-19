from datetime import datetime
from app.extensions import db


class Sale(db.Model):
    """A single sale line item. Aggregated to compute revenue, profit, and demand trends."""
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    sale_price = db.Column(db.Numeric(10, 2), nullable=False)  # price per unit at time of sale
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)  # cost per unit at time of sale
    sale_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @property
    def revenue(self):
        return float(self.sale_price) * self.quantity

    @property
    def profit(self):
        return (float(self.sale_price) - float(self.cost_price)) * self.quantity

    def to_dict(self):
        return {
            "id": self.id,
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine.name if self.medicine else None,
            "quantity": self.quantity,
            "revenue": self.revenue,
            "profit": self.profit,
            "sale_date": self.sale_date.isoformat(),
        }


class Purchase(db.Model):
    """A purchase order placed with a supplier to restock a medicine."""
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"))
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending")  # pending, delivered, cancelled

    def to_dict(self):
        return {
            "id": self.id,
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine.name if self.medicine else None,
            "quantity": self.quantity,
            "unit_cost": float(self.unit_cost),
            "total_cost": float(self.unit_cost) * self.quantity,
            "status": self.status,
            "order_date": self.order_date.isoformat(),
        }


class StockOutEvent(db.Model):
    """Logs when a medicine went out of stock — used for lost-sales / profit-leak estimation."""
    __tablename__ = "stock_out_events"

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)  # null = still out of stock
    estimated_lost_sales = db.Column(db.Numeric(10, 2), default=0)

    medicine = db.relationship("Medicine")

    def to_dict(self):
        return {
            "id": self.id,
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine.name if self.medicine else None,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "estimated_lost_sales": float(self.estimated_lost_sales or 0),
        }


class ChatMessage(db.Model):
    """Stores conversation history with the AI assistant, per session."""
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(80), index=True, default="default")
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }
