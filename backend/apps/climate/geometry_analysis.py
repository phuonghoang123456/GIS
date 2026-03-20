from __future__ import annotations

from requests import RequestException

from apps.common.helpers import fixed, to_float
from apps.common.responses import fail, ok
from apps.gee.services import check_status, fetch_data

from .analysis_areas import record_analysis_area_usage
from .services import parse_iso_date, tvdi_classification


def _check_gee_ready():
    status = check_status()
    if status.get("status") != "online" or not status.get("gee_initialized"):
        raise RuntimeError("GEE service is offline. Start backend/scripts/api_server.py and authenticate Earth Engine.")


def _parse_geometry_request(data: dict):
    start_date = parse_iso_date(data.get("start_date") or data.get("start"), "start_date")
    end_date = parse_iso_date(data.get("end_date") or data.get("end"), "end_date")
    if start_date > end_date:
        raise ValueError("Invalid date range: start_date must be before or equal to end_date.")

    geometry = data.get("geometry")
    if not geometry:
        raise ValueError("Missing geometry payload.")

    return {
        "geometry": geometry,
        "area_name": data.get("area_name") or data.get("name") or "Vùng phân tích tùy chọn",
        "province": data.get("province") or data.get("province_name") or data.get("name") or "Vùng tùy chọn",
        "source_type": data.get("source_type") or "geometry",
        "boundary_code": data.get("boundary_code"),
        "history_id": data.get("history_id"),
        "start_date": start_date,
        "end_date": end_date,
        "location_id": int(data.get("location_id") or 0),
    }


def _fetch_geometry_records(request, payload: dict, data_type: str):
    _check_gee_ready()
    fetch_payload = {
        "geometry": payload["geometry"],
        "area_name": payload["area_name"],
        "province": payload["province"],
        "source_type": payload["source_type"],
        "boundary_code": payload.get("boundary_code"),
        "start_date": payload["start_date"].isoformat(),
        "end_date": payload["end_date"].isoformat(),
        "location_id": payload["location_id"],
        "data_types": [data_type],
        "persist": False,
        "include_data": True,
    }
    result = fetch_data(fetch_payload)
    rows = result.get("results", {}).get(data_type, {}).get("data", [])
    if not isinstance(rows, list):
        rows = []
    rows.sort(key=lambda row: str(row.get("date", "")))

    history = None
    if getattr(request.user, "is_authenticated", False):
        history = record_analysis_area_usage(
            request.user,
            payload,
            extra_metadata={
                "analysis_type": data_type,
                "start_date": payload["start_date"].isoformat(),
                "end_date": payload["end_date"].isoformat(),
                "mode": "direct_gee_analysis",
            },
        )
    return rows, history


def rainfall_geometry_response(request):
    try:
        payload = _parse_geometry_request(request.data)
        rows, history = _fetch_geometry_records(request, payload, "rainfall")
    except ValueError as exc:
        return fail(str(exc), 400, "validation_error")
    except RuntimeError as exc:
        return fail(str(exc), 503, "gee_service_offline")
    except RequestException as exc:
        return fail("Failed to fetch data from GEE service", 502, "gee_service_error", {"message": str(exc)})

    data = [
        {
            "date": str(row.get("date", ""))[:10],
            "rainfall_mm": to_float(row.get("rainfall_mm")),
            "source": row.get("source"),
        }
        for row in rows
    ]
    total = sum(to_float(row["rainfall_mm"]) for row in data)
    average = total / len(data) if data else 0
    max_value = max((to_float(row["rainfall_mm"]) for row in data), default=0)
    return ok(
        {
            "data": data,
            "statistics": {
                "total": fixed(total, 2),
                "average": fixed(average, 2),
                "max": fixed(max_value, 2),
                "days": len(data),
            },
            "analysis_scope": {
                "mode": "geometry",
                "area_name": payload["area_name"],
                "province": payload["province"],
                "history_id": getattr(history, "id", None),
            },
        }
    )


def temperature_geometry_response(request):
    try:
        payload = _parse_geometry_request(request.data)
        rows, history = _fetch_geometry_records(request, payload, "temperature")
    except ValueError as exc:
        return fail(str(exc), 400, "validation_error")
    except RuntimeError as exc:
        return fail(str(exc), 503, "gee_service_offline")
    except RequestException as exc:
        return fail("Failed to fetch data from GEE service", 502, "gee_service_error", {"message": str(exc)})

    data = [
        {
            "date": str(row.get("date", ""))[:10],
            "temp_min": to_float(row.get("temp_min")),
            "temp_max": to_float(row.get("temp_max")),
            "temp_mean": to_float(row.get("temp_mean")),
            "source": row.get("source"),
        }
        for row in rows
    ]
    average = sum(to_float(row["temp_mean"]) for row in data) / len(data) if data else 0
    min_value = min((to_float(row["temp_min"]) for row in data), default=0)
    max_value = max((to_float(row["temp_max"]) for row in data), default=0)
    return ok(
        {
            "data": data,
            "statistics": {
                "average": fixed(average),
                "min": fixed(min_value),
                "max": fixed(max_value),
                "days": len(data),
            },
            "analysis_scope": {
                "mode": "geometry",
                "area_name": payload["area_name"],
                "province": payload["province"],
                "history_id": getattr(history, "id", None),
            },
        }
    )


def ndvi_geometry_response(request):
    try:
        payload = _parse_geometry_request(request.data)
        rows, history = _fetch_geometry_records(request, payload, "ndvi")
    except ValueError as exc:
        return fail(str(exc), 400, "validation_error")
    except RuntimeError as exc:
        return fail(str(exc), 503, "gee_service_offline")
    except RequestException as exc:
        return fail("Failed to fetch data from GEE service", 502, "gee_service_error", {"message": str(exc)})

    data = [
        {
            "date": str(row.get("date", ""))[:10],
            "ndvi_mean": to_float(row.get("ndvi_mean")),
            "ndvi_min": to_float(row.get("ndvi_min")),
            "ndvi_max": to_float(row.get("ndvi_max")),
            "ndvi_stddev": to_float(row.get("ndvi_stddev")),
            "vegetation_area_pct": to_float(row.get("vegetation_area_pct")),
            "source": row.get("source"),
        }
        for row in rows
    ]
    average = sum(to_float(row["ndvi_mean"]) for row in data) / len(data) if data else 0
    min_value = min((to_float(row["ndvi_min"]) for row in data), default=0)
    max_value = max((to_float(row["ndvi_max"]) for row in data), default=0)
    avg_vegetation = sum(to_float(row["vegetation_area_pct"]) for row in data) / len(data) if data else 0
    return ok(
        {
            "data": data,
            "statistics": {
                "average": fixed(average, 4),
                "min": fixed(min_value, 4),
                "max": fixed(max_value, 4),
                "avg_vegetation_pct": fixed(avg_vegetation, 2),
                "records": len(data),
            },
            "analysis_scope": {
                "mode": "geometry",
                "area_name": payload["area_name"],
                "province": payload["province"],
                "history_id": getattr(history, "id", None),
            },
        }
    )


def tvdi_geometry_response(request):
    try:
        payload = _parse_geometry_request(request.data)
        rows, history = _fetch_geometry_records(request, payload, "tvdi")
    except ValueError as exc:
        return fail(str(exc), 400, "validation_error")
    except RuntimeError as exc:
        return fail(str(exc), 503, "gee_service_offline")
    except RequestException as exc:
        return fail("Failed to fetch data from GEE service", 502, "gee_service_error", {"message": str(exc)})

    data = [
        {
            "date": str(row.get("date", ""))[:10],
            "tvdi_mean": to_float(row.get("tvdi_mean")),
            "tvdi_min": to_float(row.get("tvdi_min")),
            "tvdi_max": to_float(row.get("tvdi_max")),
            "lst_mean": to_float(row.get("lst_mean")),
            "drought_area_pct": to_float(row.get("drought_area_pct")),
            "drought_class": row.get("drought_class"),
            "source": row.get("source"),
        }
        for row in rows
    ]
    average = sum(to_float(row["tvdi_mean"]) for row in data) / len(data) if data else 0
    min_value = min((to_float(row["tvdi_min"]) for row in data), default=0)
    max_value = max((to_float(row["tvdi_max"]) for row in data), default=0)
    avg_lst = sum(to_float(row["lst_mean"]) for row in data) / len(data) if data else 0
    drought_days = len([row for row in data if row["drought_class"] in ("severe", "extreme")])
    drought_pct = (drought_days / len(data) * 100) if data else 0
    return ok(
        {
            "data": data,
            "statistics": {
                "average": fixed(average, 4),
                "min": fixed(min_value, 4),
                "max": fixed(max_value, 4),
                "avg_lst": fixed(avg_lst, 2),
                "drought_days": drought_days,
                "drought_pct": fixed(drought_pct, 2),
                "classification": tvdi_classification(average),
                "records": len(data),
            },
            "analysis_scope": {
                "mode": "geometry",
                "area_name": payload["area_name"],
                "province": payload["province"],
                "history_id": getattr(history, "id", None),
            },
        }
    )
