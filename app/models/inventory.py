from datetime import date
from app.extensions import db


class Medicine(db.Model):
    """A medicine/SKU carried by the pharmacy."""
    __tablename__ = "medicines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    category = db.Column(db.String(80))  # e.g. Antibiotic, Painkiller, OTC
    unit = db.Column(db.String(20), default="strip")  # strip, bottle, packet
    reorder_level = db.Column(db.Integer, default=20)
    ideal_stock_level = db.Column(db.Integer, default=100)
    unit_cost = db.Column(db.Numeric(10, 2), default=0)
    unit_price = db.Column(db.Numeric(10, 2), default=0)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"))

    batches = db.relationship("StockBatch", backref="medicine", lazy=True, cascade="all, delete-orphan")
    sales = db.relationship("Sale", backref="medicine", lazy=True)
    purchases = db.relationship("Purchase", backref="medicine", lazy=True)

    @property
    def current_stock(self):
        return sum(b.quantity for b in self.batches)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "unit": self.unit,
            "current_stock": self.current_stock,
            "reorder_level": self.reorder_level,
            "ideal_stock_level": self.ideal_stock_level,
            "unit_cost": float(self.unit_cost or 0),
            "unit_price": float(self.unit_price or 0),
        }


class StockBatch(db.Model):
    """A specific batch of a medicine with its own expiry date — needed for expiry-risk tracking."""
    __tablename__ = "stock_batches"

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    batch_number = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=0)
    expiry_date = db.Column(db.Date, nullable=False)
    received_date = db.Column(db.Date, default=date.today)

    def days_to_expiry(self):
        return (self.expiry_date - date.today()).days

    def to_dict(self):
        return {
            "id": self.id,
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine.name if self.medicine else None,
            "batch_number": self.batch_number,
            "quantity": self.quantity,
            "expiry_date": self.expiry_date.isoformat(),
            "days_to_expiry": self.days_to_expiry(),
        }


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    contact = db.Column(db.String(100))
    reliability_score = db.Column(db.Float, default=4.0)  # out of 5
    avg_delivery_days = db.Column(db.Integer, default=3)

    medicines = db.relationship("Medicine", backref="supplier", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "reliability_score": self.reliability_score,
            "avg_delivery_days": self.avg_delivery_days,
        }
