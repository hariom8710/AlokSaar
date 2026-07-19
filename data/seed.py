"""
Seed the PostgreSQL database with realistic demo data so the dashboard,
chat assistant, and forecasting features have something meaningful to work
with immediately after setup.

Run with:  python -m data.seed
"""
import random
from datetime import date, datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import Medicine, StockBatch, Supplier, Sale, Purchase, StockOutEvent

random.seed(42)

MEDICINES = [
    # name, category, unit, reorder, ideal, cost, price
    ("Paracetamol 650", "Painkiller", "strip", 40, 150, 8.0, 15.0),
    ("Amoxicillin 500", "Antibiotic", "strip", 25, 80, 22.0, 38.0),
    ("ORS Sachet", "OTC", "packet", 50, 200, 6.0, 12.0),
    ("Cough Syrup", "OTC", "bottle", 15, 60, 45.0, 75.0),
    ("Vitamin C 500", "Supplement", "strip", 20, 100, 18.0, 32.0),
    ("Calcium + D3", "Supplement", "strip", 20, 100, 25.0, 45.0),
    ("Ibuprofen 400", "Painkiller", "strip", 30, 120, 12.0, 22.0),
    ("Azithromycin 500", "Antibiotic", "strip", 15, 50, 35.0, 60.0),
    ("Cetirizine 10", "Antihistamine", "strip", 25, 100, 9.0, 18.0),
    ("Omeprazole 20", "Antacid", "strip", 20, 90, 15.0, 28.0),
    ("Metformin 500", "Chronic-care", "strip", 30, 120, 14.0, 25.0),
    ("Insulin Glargine", "Chronic-care", "vial", 8, 25, 280.0, 420.0),
]

SUPPLIERS = [
    ("MedPlus Distributors", "orders@medplusdist.example", 4.5, 2),
    ("HealthLine Pharma Supply", "sales@healthlinepharma.example", 4.1, 3),
    ("Apex Wholesale Medicines", "contact@apexwholesale.example", 3.7, 4),
]


def seed():
    app = create_app()
    with app.app_context():
        print("Dropping and recreating all tables...")
        db.drop_all()
        db.create_all()

        # Suppliers
        suppliers = []
        for name, contact, reliability, lead_days in SUPPLIERS:
            s = Supplier(name=name, contact=contact, reliability_score=reliability, avg_delivery_days=lead_days)
            db.session.add(s)
            suppliers.append(s)
        db.session.commit()

        # Medicines
        medicines = []
        for name, category, unit, reorder, ideal, cost, price in MEDICINES:
            m = Medicine(
                name=name,
                category=category,
                unit=unit,
                reorder_level=reorder,
                ideal_stock_level=ideal,
                unit_cost=cost,
                unit_price=price,
                supplier_id=random.choice(suppliers).id,
            )
            db.session.add(m)
            medicines.append(m)
        db.session.commit()

        by_name = {m.name: m for m in medicines}

        # Stock batches — mix of healthy, low, and near-expiry stock
        today = date.today()

        def add_batch(med, qty, expiry_days, batch_prefix):
            batch = StockBatch(
                medicine_id=med.id,
                batch_number=f"{batch_prefix}-{random.randint(1000,9999)}",
                quantity=qty,
                expiry_date=today + timedelta(days=expiry_days),
                received_date=today - timedelta(days=random.randint(10, 120)),
            )
            db.session.add(batch)

        # Healthy stock for most items
        add_batch(by_name["Paracetamol 650"], 180, 400, "PCM")
        add_batch(by_name["Amoxicillin 500"], 60, 300, "AMX")
        add_batch(by_name["ORS Sachet"], 220, 500, "ORS")
        add_batch(by_name["Ibuprofen 400"], 140, 350, "IBU")
        add_batch(by_name["Cetirizine 10"], 110, 300, "CTZ")
        add_batch(by_name["Metformin 500"], 130, 250, "MET")

        # Low stock items (matches poster: "Low Stock Items: 7")
        add_batch(by_name["Cough Syrup"], 10, 200, "CGH")
        add_batch(by_name["Azithromycin 500"], 8, 180, "AZM")
        add_batch(by_name["Omeprazole 20"], 12, 220, "OMP")
        add_batch(by_name["Insulin Glargine"], 5, 300, "INS")

        # Near-expiry batches (matches poster: "Expiring Items: 4")
        add_batch(by_name["Vitamin C 500"], 45, 12, "VTC")   # expires in 12 days - imminent
        add_batch(by_name["Calcium + D3"], 38, 25, "CAL")    # expires in 25 days
        add_batch(by_name["Paracetamol 650"], 20, 40, "PCM")  # expires in 40 days
        add_batch(by_name["Cough Syrup"], 15, 70, "CGH")     # expires in 70 days

        # Dead stock: Vitamin C and Calcium overstocked, matches poster hint about them
        add_batch(by_name["Vitamin C 500"], 60, 300, "VTC")
        add_batch(by_name["Calcium + D3"], 55, 280, "CAL")

        db.session.commit()

        # Sales history: last 45 days, weighted so fast movers sell more,
        # Vitamin C / Calcium barely sell (dead stock), fever meds trend up recently
        print("Generating 45 days of sales history...")
        fast_movers = ["Paracetamol 650", "ORS Sachet", "Cetirizine 10", "Ibuprofen 400", "Metformin 500"]
        medium_movers = ["Amoxicillin 500", "Omeprazole 20", "Cough Syrup", "Azithromycin 500"]
        slow_movers = ["Vitamin C 500", "Calcium + D3", "Insulin Glargine"]

        for day_offset in range(45, 0, -1):
            sale_day = datetime.utcnow() - timedelta(days=day_offset)
            # simulate a recent fever/cough uptick in the last 10 days (drives "profit low this month" story)
            seasonal_boost = 1.4 if day_offset <= 10 else 1.0

            for name in fast_movers:
                med = by_name[name]
                base_qty = random.randint(4, 12)
                if name == "Paracetamol 650":
                    base_qty = int(base_qty * seasonal_boost)
                qty = max(1, base_qty)
                cost = float(med.unit_cost)
                price = float(med.unit_price)
                db.session.add(Sale(
                    medicine_id=med.id, quantity=qty,
                    sale_price=price, cost_price=cost,
                    sale_date=sale_day + timedelta(hours=random.randint(9, 20)),
                ))

            for name in medium_movers:
                med = by_name[name]
                if random.random() < 0.6:  # not every day
                    qty = random.randint(1, 5)
                    db.session.add(Sale(
                        medicine_id=med.id, quantity=qty,
                        sale_price=float(med.unit_price), cost_price=float(med.unit_cost),
                        sale_date=sale_day + timedelta(hours=random.randint(9, 20)),
                    ))

            # slow movers: almost no sales in the last 60 days (dead stock)
            for name in slow_movers:
                if name == "Insulin Glargine" and random.random() < 0.15:
                    med = by_name[name]
                    db.session.add(Sale(
                        medicine_id=med.id, quantity=1,
                        sale_price=float(med.unit_price), cost_price=float(med.unit_cost),
                        sale_date=sale_day + timedelta(hours=random.randint(9, 20)),
                    ))
                # Vitamin C / Calcium: intentionally no recent sales -> dead stock signal

        db.session.commit()

        # A couple of purchase orders
        db.session.add(Purchase(
            medicine_id=by_name["Cough Syrup"].id,
            supplier_id=suppliers[0].id,
            quantity=100, unit_cost=45.0,
            order_date=datetime.utcnow() - timedelta(days=2),
            status="pending",
        ))
        db.session.add(Purchase(
            medicine_id=by_name["Paracetamol 650"].id,
            supplier_id=suppliers[1].id,
            quantity=200, unit_cost=8.0,
            order_date=datetime.utcnow() - timedelta(days=20),
            status="delivered",
        ))
        db.session.commit()

        # Stock-out event: Cough Syrup / fever items were out of stock for a few days
        # (feeds the "Fever medicines were out of stock for 4 days" example in the poster)
        db.session.add(StockOutEvent(
            medicine_id=by_name["Cough Syrup"].id,
            start_date=today - timedelta(days=14),
            end_date=today - timedelta(days=10),
            estimated_lost_sales=12000.0,
        ))
        db.session.commit()

        print("Seed complete.")
        print(f"  Medicines: {Medicine.query.count()}")
        print(f"  Suppliers: {Supplier.query.count()}")
        print(f"  Stock batches: {StockBatch.query.count()}")
        print(f"  Sales records: {Sale.query.count()}")
        print(f"  Purchases: {Purchase.query.count()}")
        print(f"  Stock-out events: {StockOutEvent.query.count()}")


if __name__ == "__main__":
    seed()
