"""
CSV Import service — parses uploaded CSV files and appends rows into the
database. Append-only: never deletes or overwrites existing records.
"""
import csv
import io
from datetime import datetime, date
from app.extensions import db
from app.models import Medicine, StockBatch, Supplier, Sale, Purchase, StockOutEvent


class ImportResult:
    def __init__(self):
        self.inserted = 0
        self.skipped = 0
        self.errors = []

    def to_dict(self):
        return {"inserted": self.inserted, "skipped": self.skipped, "errors": self.errors}


def _parse_date(value):
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: '{value}'")


def _get_medicine_by_name(name):
    return Medicine.query.filter_by(name=name.strip()).first()


def _get_supplier_by_name(name):
    if not name or not name.strip():
        return None
    return Supplier.query.filter_by(name=name.strip()).first()


def _read_rows(file_stream):
    text = io.TextIOWrapper(file_stream, encoding="utf-8-sig")
    return list(csv.DictReader(text))


def import_suppliers(file_stream):
    result = ImportResult()
    rows = _read_rows(file_stream)
    for i, row in enumerate(rows, start=2):  # row 1 is header
        try:
            name = (row.get("supplier_name") or "").strip()
            if not name:
                result.errors.append(f"Row {i}: missing supplier_name")
                result.skipped += 1
                continue
            supplier = Supplier(
                name=name,
                contact=(row.get("contact") or "").strip() or None,
                reliability_score=float(row["reliability_score"]) if row.get("reliability_score") else 4.0,
                avg_delivery_days=int(row["avg_delivery_days"]) if row.get("avg_delivery_days") else 3,
            )
            db.session.add(supplier)
            result.inserted += 1
        except Exception as e:
            result.errors.append(f"Row {i}: {e}")
            result.skipped += 1
    db.session.commit()
    return result


def import_medicines(file_stream):
    result = ImportResult()
    rows = _read_rows(file_stream)
    for i, row in enumerate(rows, start=2):
        try:
            name = (row.get("medicine_name") or "").strip()
            if not name:
                result.errors.append(f"Row {i}: missing medicine_name")
                result.skipped += 1
                continue
            if _get_medicine_by_name(name):
                result.errors.append(f"Row {i}: '{name}' already exists, skipped")
                result.skipped += 1
                continue

            supplier = _get_supplier_by_name(row.get("supplier_name"))
            medicine = Medicine(
                name=name,
                category=(row.get("category") or "").strip() or None,
                unit=(row.get("unit") or "strip").strip(),
                reorder_level=int(row["reorder_level"]),
                ideal_stock_level=int(row["ideal_stock_level"]),
                unit_cost=float(row["unit_cost"]),
                unit_price=float(row["unit_price"]),
                supplier_id=supplier.id if supplier else None,
            )
            db.session.add(medicine)
            result.inserted += 1
        except KeyError as e:
            result.errors.append(f"Row {i}: missing required column {e}")
            result.skipped += 1
        except Exception as e:
            result.errors.append(f"Row {i}: {e}")
            result.skipped += 1
    db.session.commit()
    return result


def import_stock_batches(file_stream):
    result = ImportResult()
    rows = _read_rows(file_stream)
    for i, row in enumerate(rows, start=2):
        try:
            med_name = (row.get("medicine_name") or "").strip()
            medicine = _get_medicine_by_name(med_name)
            if not medicine:
                result.errors.append(f"Row {i}: medicine '{med_name}' not found — import medicines.csv first")
                result.skipped += 1
                continue

            expiry = _parse_date(row.get("expiry_date"))
            if not expiry:
                result.errors.append(f"Row {i}: missing/invalid expiry_date")
                result.skipped += 1
                continue

            received = _parse_date(row.get("received_date")) or datetime.utcnow()

            batch = StockBatch(
                medicine_id=medicine.id,
                batch_number=(row.get("batch_number") or "").strip() or None,
                quantity=int(row["quantity"]),
                expiry_date=expiry.date(),
                received_date=received.date(),
            )
            db.session.add(batch)
            result.inserted += 1
        except Exception as e:
            result.errors.append(f"Row {i}: {e}")
            result.skipped += 1
    db.session.commit()
    return result


def import_sales(file_stream):
    result = ImportResult()
    rows = _read_rows(file_stream)
    for i, row in enumerate(rows, start=2):
        try:
            med_name = (row.get("medicine_name") or "").strip()
            medicine = _get_medicine_by_name(med_name)
            if not medicine:
                result.errors.append(f"Row {i}: medicine '{med_name}' not found — import medicines.csv first")
                result.skipped += 1
                continue

            sale_date = _parse_date(row.get("sale_date"))
            if not sale_date:
                result.errors.append(f"Row {i}: missing/invalid sale_date")
                result.skipped += 1
                continue

            sale = Sale(
                medicine_id=medicine.id,
                quantity=int(row["quantity"]),
                sale_price=float(row["sale_price"]),
                cost_price=float(row["cost_price"]),
                sale_date=sale_date,
            )
            db.session.add(sale)
            result.inserted += 1
        except Exception as e:
            result.errors.append(f"Row {i}: {e}")
            result.skipped += 1
    db.session.commit()
    return result


def import_purchases(file_stream):
    result = ImportResult()
    rows = _read_rows(file_stream)
    for i, row in enumerate(rows, start=2):
        try:
            med_name = (row.get("medicine_name") or "").strip()
            medicine = _get_medicine_by_name(med_name)
            if not medicine:
                result.errors.append(f"Row {i}: medicine '{med_name}' not found — import medicines.csv first")
                result.skipped += 1
                continue

            supplier = _get_supplier_by_name(row.get("supplier_name"))
            order_date = _parse_date(row.get("order_date")) or datetime.utcnow()

            purchase = Purchase(
                medicine_id=medicine.id,
                supplier_id=supplier.id if supplier else None,
                quantity=int(row["quantity"]),
                unit_cost=float(row["unit_cost"]),
                order_date=order_date,
                status=(row.get("status") or "pending").strip(),
            )
            db.session.add(purchase)
            result.inserted += 1
        except Exception as e:
            result.errors.append(f"Row {i}: {e}")
            result.skipped += 1
    db.session.commit()
    return result


def import_stock_out_events(file_stream):
    result = ImportResult()
    rows = _read_rows(file_stream)
    for i, row in enumerate(rows, start=2):
        try:
            med_name = (row.get("medicine_name") or "").strip()
            medicine = _get_medicine_by_name(med_name)
            if not medicine:
                result.errors.append(f"Row {i}: medicine '{med_name}' not found — import medicines.csv first")
                result.skipped += 1
                continue

            start = _parse_date(row.get("start_date"))
            if not start:
                result.errors.append(f"Row {i}: missing/invalid start_date")
                result.skipped += 1
                continue
            end = _parse_date(row.get("end_date"))

            event = StockOutEvent(
                medicine_id=medicine.id,
                start_date=start.date(),
                end_date=end.date() if end else None,
                estimated_lost_sales=float(row["estimated_lost_sales"]) if row.get("estimated_lost_sales") else 0,
            )
            db.session.add(event)
            result.inserted += 1
        except Exception as e:
            result.errors.append(f"Row {i}: {e}")
            result.skipped += 1
    db.session.commit()
    return result


IMPORTERS = {
    "suppliers": import_suppliers,
    "medicines": import_medicines,
    "stock_batches": import_stock_batches,
    "sales": import_sales,
    "purchases": import_purchases,
    "stock_out_events": import_stock_out_events,
}
