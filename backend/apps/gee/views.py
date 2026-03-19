from requests import RequestException
from rest_framework.views import APIView

from apps.common.responses import fail, ok

from .services import check_status, fetch_data, validate_fetch_payload


def _gee_unavailable_response(status_payload: dict):
    return fail(
        "Python GEE API is not available",
        503,
        "gee_service_offline",
        {"message": "Please start the Python API server: python backend/scripts/api_server.py", "status": status_payload},
    )


class GeeStatusView(APIView):
    permission_classes = []

    def get(self, request):
        return ok(check_status())


class GeeFetchView(APIView):
    permission_classes = []

    def post(self, request):
        payload = request.data
        valid, error_payload = validate_fetch_payload(payload)
        if not valid:
            return fail(error_payload["error"], 400, "validation_error", error_payload)

        status = check_status()
        if status.get("status") != "online":
            return _gee_unavailable_response(status)

        try:
            result = fetch_data(payload)
            return ok(
                {
                    "success": True,
                    "message": "Data fetched and saved successfully",
                    "province": payload["province"],
                    "location_id": payload["location_id"],
                    "period": f'{payload["start_date"]} to {payload["end_date"]}',
                    "results": result.get("results", {}),
                }
            )
        except RequestException as exc:
            return fail("Failed to fetch data from GEE", 500, "gee_fetch_failed", {"message": str(exc)})


class GeeFetchRainfallView(APIView):
    permission_classes = []

    def post(self, request):
        payload = dict(request.data)
        payload["data_types"] = ["rainfall"]
        valid, error_payload = validate_fetch_payload(payload)
        if not valid:
            return fail(error_payload["error"], 400, "validation_error", error_payload)
        status = check_status()
        if status.get("status") != "online":
            return _gee_unavailable_response(status)
        try:
            return ok(fetch_data(payload))
        except RequestException as exc:
            return fail("Failed to fetch rainfall data", 500, "gee_fetch_failed", {"message": str(exc)})


class GeeFetchTemperatureView(APIView):
    permission_classes = []

    def post(self, request):
        payload = dict(request.data)
        payload["data_types"] = ["temperature"]
        valid, error_payload = validate_fetch_payload(payload)
        if not valid:
            return fail(error_payload["error"], 400, "validation_error", error_payload)
        status = check_status()
        if status.get("status") != "online":
            return _gee_unavailable_response(status)
        try:
            return ok(fetch_data(payload))
        except RequestException as exc:
            return fail("Failed to fetch temperature data", 500, "gee_fetch_failed", {"message": str(exc)})


class GeeFetchAllView(APIView):
    permission_classes = []

    def post(self, request):
        payload = dict(request.data)
        payload["data_types"] = ["rainfall", "temperature", "soil_moisture", "ndvi", "tvdi"]
        valid, error_payload = validate_fetch_payload(payload)
        if not valid:
            return fail(error_payload["error"], 400, "validation_error", error_payload)
        status = check_status()
        if status.get("status") != "online":
            return _gee_unavailable_response(status)
        try:
            return ok(fetch_data(payload))
        except RequestException as exc:
            return fail("Failed to fetch all data", 500, "gee_fetch_failed", {"message": str(exc)})
