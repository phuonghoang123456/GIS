import re
from datetime import datetime

import requests
from django.conf import settings


def check_status():
    try:
        response = requests.get(f"{settings.PYTHON_GEE_API_URL}/status", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {"status": "offline", "gee_initialized": False}


def fetch_data(payload: dict):
    response = requests.post(
        f"{settings.PYTHON_GEE_API_URL}/fetch-data",
        json=payload,
        timeout=600,
    )
    response.raise_for_status()
    return response.json()


def validate_fetch_payload(payload: dict):
    required = ["province", "location_id", "start_date", "end_date"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return False, {"error": "Missing required fields", "required": required}

    try:
        payload["location_id"] = int(payload["location_id"])
    except (TypeError, ValueError):
        return False, {"error": "location_id must be an integer"}

    data_types = payload.get("data_types")
    if not isinstance(data_types, list) or not data_types:
        return False, {"error": "data_types must be a non-empty array", "example": ["rainfall", "temperature"]}
    allowed_types = {"rainfall", "temperature", "soil_moisture", "ndvi", "tvdi"}
    invalid_types = [value for value in data_types if value not in allowed_types]
    if invalid_types:
        return False, {"error": "Invalid data_types", "invalid": invalid_types, "allowed": sorted(allowed_types)}

    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if not date_re.match(payload["start_date"]) or not date_re.match(payload["end_date"]):
        return False, {"error": "Invalid date format. Use YYYY-MM-DD"}
    try:
        start_date = datetime.strptime(payload["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(payload["end_date"], "%Y-%m-%d").date()
    except ValueError:
        return False, {"error": "Invalid calendar date. Use YYYY-MM-DD"}
    if start_date > end_date:
        return False, {"error": "Invalid date range: start_date must be before or equal to end_date"}

    return True, None
