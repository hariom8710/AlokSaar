import os
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request, current_app
from app.services.csv_import import IMPORTERS

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/upload")
def upload_page():
    return render_template("upload.html")


@upload_bp.route("/api/upload/<csv_type>", methods=["POST"])
def upload_csv(csv_type):
    if csv_type not in IMPORTERS:
        return jsonify({"error": f"Unknown CSV type '{csv_type}'"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "File must be a .csv"}), 400

    uploads_dir = os.path.join(current_app.root_path, "..", "uploaded_files", csv_type)
    os.makedirs(uploads_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    saved_path = os.path.join(uploads_dir, f"{timestamp}_{file.filename}")
    file.save(saved_path)

    try:
        with open(saved_path, "rb") as f:
            result = IMPORTERS[csv_type](f)
    except Exception as e:
        return jsonify({"error": f"Import failed: {e}", "saved_to": saved_path}), 500

    response = result.to_dict()
    response["saved_to"] = saved_path
    return jsonify(response)
