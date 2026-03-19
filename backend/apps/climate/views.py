from __future__ import annotations

from datetime import date

from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from requests import RequestException
from rest_framework.views import APIView

from apps.common.helpers import calculate_trend, fixed, to_float
from apps.common.responses import fail, ok
from apps.gee.services import check_status, fetch_data

from .models import Location, NdviData, RainfallData, SoilMoistureData, TemperatureData, TvdiData
from .services import dashboard_timeseries, ndvi_classification, parse_iso_date, tvdi_classification


def _parse_int_param(value, name: str, minimum: int | None = None, maximum: int | None = None) -> int:
    if value is None:
        raise ValueError(f"Missing required parameter: {name}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {name}. Must be an integer.") from exc

    if minimum is not None and parsed < minimum:
        raise ValueError(f"Invalid {name}. Must be >= {minimum}.")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"Invalid {name}. Must be <= {maximum}.")
    return parsed


def _get_range_params(request):
    location_id_raw = request.query_params.get("location_id")
    start = request.query_params.get("start")
    end = request.query_params.get("end")
    location_id = _parse_int_param(location_id_raw, "location_id", minimum=1)
    start_date = parse_iso_date(start, "start")
    end_date = parse_iso_date(end, "end")
    if start_date > end_date:
        raise ValueError("Invalid date range: start must be before or equal to end.")
    return location_id, start_date, end_date


def _is_gee_source(request) -> bool:
    return request.query_params.get("source", "db").lower() == "gee"


def _resolve_province(location_id: int, province_query: str | None) -> str | None:
    if province_query:
        return province_query
    return Location.objects.filter(id=location_id).values_list("province", flat=True).first()


def _fetch_gee_records(
    location_id: int,
    start: date,
    end: date,
    data_type: str,
    province_query: str | None,
):
    province = _resolve_province(location_id, province_query)
    if not province:
        raise ValueError("Missing province. Provide `province` query param or create location with province.")

    status = check_status()
    if status.get("status") != "online" or not status.get("gee_initialized"):
        raise RuntimeError("GEE service is offline. Start backend/scripts/api_server.py and authenticate Earth Engine.")

    payload = {
        "province": province,
        "location_id": location_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "data_types": [data_type],
        "persist": False,
        "include_data": True,
    }
    result = fetch_data(payload)
    records = result.get("results", {}).get(data_type, {}).get("data", [])
    if not isinstance(records, list):
        records = []
    records.sort(key=lambda row: str(row.get("date", "")))
    return records


class LocationsView(APIView):
    permission_classes = []

    def get(self, request):
        rows = list(Location.objects.values("id", "name", "province").order_by("name"))
        return ok(rows)


class LocationDetailView(APIView):
    permission_classes = []

    def get(self, request, location_id: int):
        location = Location.objects.filter(id=location_id).values().first()
        if not location:
            return fail("Location not found", 404, "not_found")
        return ok(location)


class RainfallRangeView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id, start, end = _get_range_params(request)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        if _is_gee_source(request):
            try:
                rows = _fetch_gee_records(
                    location_id=location_id,
                    start=start,
                    end=end,
                    data_type="rainfall",
                    province_query=request.query_params.get("province"),
                )
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
        else:
            queryset = RainfallData.objects.filter(location_id=location_id, date__range=[start, end]).order_by("date")
            data = [
                {"date": row.date, "rainfall_mm": to_float(row.rainfall_mm), "source": row.source}
                for row in queryset
            ]

        total = sum(to_float(row["rainfall_mm"]) for row in data)
        avg = total / len(data) if data else 0
        max_value = max((to_float(row["rainfall_mm"]) for row in data), default=0)

        return ok(
            {
                "data": data,
                "statistics": {
                    "total": fixed(total, 2),
                    "average": fixed(avg, 2),
                    "max": fixed(max_value, 2),
                    "days": len(data),
                },
            }
        )


class RainfallMonthlyView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id = _parse_int_param(request.query_params.get("location_id"), "location_id", minimum=1)
            year = _parse_int_param(request.query_params.get("year"), "year", minimum=1900, maximum=2100)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        if _is_gee_source(request):
            try:
                rows = _fetch_gee_records(
                    location_id=location_id,
                    start=date(year, 1, 1),
                    end=date(year, 12, 31),
                    data_type="rainfall",
                    province_query=request.query_params.get("province"),
                )
            except ValueError as exc:
                return fail(str(exc), 400, "validation_error")
            except RuntimeError as exc:
                return fail(str(exc), 503, "gee_service_offline")
            except RequestException as exc:
                return fail("Failed to fetch data from GEE service", 502, "gee_service_error", {"message": str(exc)})

            grouped = {}
            for row in rows:
                try:
                    row_date = parse_iso_date(str(row.get("date", ""))[:10], "date")
                except ValueError:
                    continue
                month = row_date.month
                grouped.setdefault(month, [])
                grouped[month].append(to_float(row.get("rainfall_mm")))
            result = [
                {
                    "month": month,
                    "total": fixed(sum(values), 2),
                    "average": fixed(sum(values) / len(values) if values else 0, 2),
                    "max": fixed(max(values) if values else 0, 2),
                    "days": len(values),
                }
                for month, values in sorted(grouped.items())
            ]
        else:
            rows = (
                RainfallData.objects.filter(location_id=location_id, date__year=year)
                .annotate(month=ExtractMonth("date"))
                .values("month")
                .annotate(
                    total_rainfall=Sum("rainfall_mm"),
                    avg_rainfall=Avg("rainfall_mm"),
                    max_rainfall=Max("rainfall_mm"),
                    days_count=Count("id"),
                )
                .order_by("month")
            )
            result = [
                {
                    "month": int(row["month"]),
                    "total": fixed(row["total_rainfall"], 2),
                    "average": fixed(row["avg_rainfall"], 2),
                    "max": fixed(row["max_rainfall"], 2),
                    "days": int(row["days_count"]),
                }
                for row in rows
            ]
        return ok({"year": year, "monthly_data": result})


class RainfallYearlyView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id = _parse_int_param(request.query_params.get("location_id"), "location_id", minimum=1)
            start_year = _parse_int_param(request.query_params.get("start_year"), "start_year", minimum=1900, maximum=2100)
            end_year = _parse_int_param(request.query_params.get("end_year"), "end_year", minimum=1900, maximum=2100)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")
        if start_year > end_year:
            return fail("Invalid year range: start_year must be <= end_year", 400, "validation_error")

        rows = (
            RainfallData.objects.filter(location_id=location_id, date__year__range=[start_year, end_year])
            .annotate(year=ExtractYear("date"))
            .values("year")
            .annotate(total_rainfall=Sum("rainfall_mm"), avg_rainfall=Avg("rainfall_mm"), max_rainfall=Max("rainfall_mm"))
            .order_by("year")
        )
        output = [
            {
                "year": int(row["year"]),
                "total": fixed(row["total_rainfall"], 2),
                "average": fixed(row["avg_rainfall"], 2),
                "max": fixed(row["max_rainfall"], 2),
            }
            for row in rows
        ]
        trend = calculate_trend([{"x": row["year"], "y": to_float(row["total"])} for row in output])
        return ok({"yearly_data": output, "trend": trend})


class RainfallComparePeriodsView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id = _parse_int_param(request.query_params.get("location_id"), "location_id", minimum=1)
            start1 = parse_iso_date(request.query_params.get("start1"), "start1")
            end1 = parse_iso_date(request.query_params.get("end1"), "end1")
            start2 = parse_iso_date(request.query_params.get("start2"), "start2")
            end2 = parse_iso_date(request.query_params.get("end2"), "end2")
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")
        if start1 > end1 or start2 > end2:
            return fail("Invalid date range: start date must be before or equal to end date", 400, "validation_error")

        data1 = RainfallData.objects.filter(location_id=location_id, date__range=[start1, end1])
        data2 = RainfallData.objects.filter(location_id=location_id, date__range=[start2, end2])

        total1 = sum(to_float(row.rainfall_mm) for row in data1)
        total2 = sum(to_float(row.rainfall_mm) for row in data2)
        avg1 = total1 / data1.count() if data1.exists() else 0
        avg2 = total2 / data2.count() if data2.exists() else 0
        percentage_change = ((total1 - total2) / total2) * 100 if total2 else 0

        return ok(
            {
                "period_1": {"start": start1, "end": end1, "total": fixed(total1), "average": fixed(avg1), "days": data1.count()},
                "period_2": {"start": start2, "end": end2, "total": fixed(total2), "average": fixed(avg2), "days": data2.count()},
                "comparison": {"difference": fixed(total1 - total2), "percentage_change": fixed(percentage_change)},
            }
        )


class RainfallCompareLocationsView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location1 = _parse_int_param(request.query_params.get("location1"), "location1", minimum=1)
            location2 = _parse_int_param(request.query_params.get("location2"), "location2", minimum=1)
            start = parse_iso_date(request.query_params.get("start"), "start")
            end = parse_iso_date(request.query_params.get("end"), "end")
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")
        if start > end:
            return fail("Invalid date range: start must be before or equal to end", 400, "validation_error")

        data1 = RainfallData.objects.filter(location_id=location1, date__range=[start, end])
        data2 = RainfallData.objects.filter(location_id=location2, date__range=[start, end])

        total1 = sum(to_float(row.rainfall_mm) for row in data1)
        total2 = sum(to_float(row.rainfall_mm) for row in data2)

        return ok(
            {
                "location_1": {
                    "id": location1,
                    "total": fixed(total1),
                    "average": fixed(total1 / data1.count() if data1.exists() else 0),
                },
                "location_2": {
                    "id": location2,
                    "total": fixed(total2),
                    "average": fixed(total2 / data2.count() if data2.exists() else 0),
                },
                "difference": fixed(total1 - total2),
            }
        )


class TemperatureRangeView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id, start, end = _get_range_params(request)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        if _is_gee_source(request):
            try:
                rows = _fetch_gee_records(
                    location_id=location_id,
                    start=start,
                    end=end,
                    data_type="temperature",
                    province_query=request.query_params.get("province"),
                )
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
        else:
            queryset = TemperatureData.objects.filter(location_id=location_id, date__range=[start, end]).order_by("date")
            data = [
                {
                    "date": row.date,
                    "temp_min": to_float(row.temp_min),
                    "temp_max": to_float(row.temp_max),
                    "temp_mean": to_float(row.temp_mean),
                    "source": row.source,
                }
                for row in queryset
            ]
        average = sum(to_float(r["temp_mean"]) for r in data) / len(data) if data else 0
        min_value = min((to_float(r["temp_min"]) for r in data), default=0)
        max_value = max((to_float(r["temp_max"]) for r in data), default=0)
        return ok(
            {
                "data": data,
                "statistics": {
                    "average": fixed(average),
                    "min": fixed(min_value),
                    "max": fixed(max_value),
                    "days": len(data),
                },
            }
        )


class TemperatureMonthlyView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id = _parse_int_param(request.query_params.get("location_id"), "location_id", minimum=1)
            year = _parse_int_param(request.query_params.get("year"), "year", minimum=1900, maximum=2100)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        if _is_gee_source(request):
            try:
                rows = _fetch_gee_records(
                    location_id=location_id,
                    start=date(year, 1, 1),
                    end=date(year, 12, 31),
                    data_type="temperature",
                    province_query=request.query_params.get("province"),
                )
            except ValueError as exc:
                return fail(str(exc), 400, "validation_error")
            except RuntimeError as exc:
                return fail(str(exc), 503, "gee_service_offline")
            except RequestException as exc:
                return fail("Failed to fetch data from GEE service", 502, "gee_service_error", {"message": str(exc)})

            grouped = {}
            for row in rows:
                try:
                    row_date = parse_iso_date(str(row.get("date", ""))[:10], "date")
                except ValueError:
                    continue
                month = row_date.month
                grouped.setdefault(month, {"temp_mean": [], "temp_min": [], "temp_max": []})
                grouped[month]["temp_mean"].append(to_float(row.get("temp_mean")))
                grouped[month]["temp_min"].append(to_float(row.get("temp_min")))
                grouped[month]["temp_max"].append(to_float(row.get("temp_max")))

            payload = []
            for month, stats in sorted(grouped.items()):
                mean_values = stats["temp_mean"]
                min_values = stats["temp_min"]
                max_values = stats["temp_max"]
                payload.append(
                    {
                        "month": month,
                        "avg_temp": fixed(sum(mean_values) / len(mean_values) if mean_values else 0),
                        "avg_min": fixed(sum(min_values) / len(min_values) if min_values else 0),
                        "avg_max": fixed(sum(max_values) / len(max_values) if max_values else 0),
                        "min_temp": fixed(min(min_values) if min_values else 0),
                        "max_temp": fixed(max(max_values) if max_values else 0),
                    }
                )
        else:
            rows = (
                TemperatureData.objects.filter(location_id=location_id, date__year=year)
                .annotate(month=ExtractMonth("date"))
                .values("month")
                .annotate(
                    avg_temp=Avg("temp_mean"),
                    avg_min=Avg("temp_min"),
                    avg_max=Avg("temp_max"),
                    min_temp=Min("temp_min"),
                    max_temp=Max("temp_max"),
                )
                .order_by("month")
            )
            payload = [
                {
                    "month": int(row["month"]),
                    "avg_temp": fixed(row["avg_temp"]),
                    "avg_min": fixed(row["avg_min"]),
                    "avg_max": fixed(row["avg_max"]),
                    "min_temp": fixed(row["min_temp"]),
                    "max_temp": fixed(row["max_temp"]),
                }
                for row in rows
            ]
        return ok({"year": year, "monthly_data": payload})


class NdviRangeView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id, start, end = _get_range_params(request)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        if _is_gee_source(request):
            try:
                rows = _fetch_gee_records(
                    location_id=location_id,
                    start=start,
                    end=end,
                    data_type="ndvi",
                    province_query=request.query_params.get("province"),
                )
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
        else:
            queryset = NdviData.objects.filter(location_id=location_id, date__range=[start, end]).order_by("date")
            data = [
                {
                    "date": row.date,
                    "ndvi_mean": to_float(row.ndvi_mean),
                    "ndvi_min": to_float(row.ndvi_min),
                    "ndvi_max": to_float(row.ndvi_max),
                    "ndvi_stddev": to_float(row.ndvi_stddev),
                    "vegetation_area_pct": to_float(row.vegetation_area_pct),
                    "source": row.source,
                }
                for row in queryset
            ]
        avg_ndvi = sum(to_float(r["ndvi_mean"]) for r in data) / len(data) if data else 0
        min_ndvi = min((to_float(r["ndvi_min"]) for r in data), default=0)
        max_ndvi = max((to_float(r["ndvi_max"]) for r in data), default=0)
        avg_veg = sum(to_float(r["vegetation_area_pct"]) for r in data) / len(data) if data else 0

        return ok(
            {
                "data": data,
                "statistics": {
                    "average": fixed(avg_ndvi, 4),
                    "min": fixed(min_ndvi, 4),
                    "max": fixed(max_ndvi, 4),
                    "avg_vegetation_pct": fixed(avg_veg, 2),
                    "classification": ndvi_classification(avg_ndvi),
                    "records": len(data),
                },
            }
        )


class NdviMonthlyView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id = _parse_int_param(request.query_params.get("location_id"), "location_id", minimum=1)
            year = _parse_int_param(request.query_params.get("year"), "year", minimum=1900, maximum=2100)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        if _is_gee_source(request):
            try:
                rows = _fetch_gee_records(
                    location_id=location_id,
                    start=date(year, 1, 1),
                    end=date(year, 12, 31),
                    data_type="ndvi",
                    province_query=request.query_params.get("province"),
                )
            except ValueError as exc:
                return fail(str(exc), 400, "validation_error")
            except RuntimeError as exc:
                return fail(str(exc), 503, "gee_service_offline")
            except RequestException as exc:
                return fail("Failed to fetch data from GEE service", 502, "gee_service_error", {"message": str(exc)})

            grouped = {}
            for row in rows:
                try:
                    row_date = parse_iso_date(str(row.get("date", ""))[:10], "date")
                except ValueError:
                    continue
                month = row_date.month
                grouped.setdefault(month, {"ndvi_mean": [], "ndvi_min": [], "ndvi_max": [], "vegetation_area_pct": []})
                grouped[month]["ndvi_mean"].append(to_float(row.get("ndvi_mean")))
                grouped[month]["ndvi_min"].append(to_float(row.get("ndvi_min")))
                grouped[month]["ndvi_max"].append(to_float(row.get("ndvi_max")))
                grouped[month]["vegetation_area_pct"].append(to_float(row.get("vegetation_area_pct")))

            payload = []
            for month, stats in sorted(grouped.items()):
                mean_values = stats["ndvi_mean"]
                min_values = stats["ndvi_min"]
                max_values = stats["ndvi_max"]
                veg_values = stats["vegetation_area_pct"]
                avg_ndvi = sum(mean_values) / len(mean_values) if mean_values else 0
                payload.append(
                    {
                        "month": month,
                        "avg_ndvi": fixed(avg_ndvi, 4),
                        "min_ndvi": fixed(min(min_values) if min_values else 0, 4),
                        "max_ndvi": fixed(max(max_values) if max_values else 0, 4),
                        "avg_veg_pct": fixed(sum(veg_values) / len(veg_values) if veg_values else 0, 2),
                        "classification": ndvi_classification(to_float(avg_ndvi)),
                    }
                )
        else:
            rows = (
                NdviData.objects.filter(location_id=location_id, date__year=year)
                .annotate(month=ExtractMonth("date"))
                .values("month")
                .annotate(avg_ndvi=Avg("ndvi_mean"), min_ndvi=Min("ndvi_min"), max_ndvi=Max("ndvi_max"), avg_veg_pct=Avg("vegetation_area_pct"))
                .order_by("month")
            )
            payload = [
                {
                    "month": int(row["month"]),
                    "avg_ndvi": fixed(row["avg_ndvi"], 4),
                    "min_ndvi": fixed(row["min_ndvi"], 4),
                    "max_ndvi": fixed(row["max_ndvi"], 4),
                    "avg_veg_pct": fixed(row["avg_veg_pct"], 2),
                    "classification": ndvi_classification(to_float(row["avg_ndvi"])),
                }
                for row in rows
            ]
        return ok({"year": year, "monthly_data": payload})


class NdviYearlyView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id = _parse_int_param(request.query_params.get("location_id"), "location_id", minimum=1)
            start_year = _parse_int_param(request.query_params.get("start_year"), "start_year", minimum=1900, maximum=2100)
            end_year = _parse_int_param(request.query_params.get("end_year"), "end_year", minimum=1900, maximum=2100)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")
        if start_year > end_year:
            return fail("Invalid year range: start_year must be <= end_year", 400, "validation_error")

        rows = (
            NdviData.objects.filter(location_id=location_id, date__year__range=[start_year, end_year])
            .annotate(year=ExtractYear("date"))
            .values("year")
            .annotate(avg_ndvi=Avg("ndvi_mean"), min_ndvi=Min("ndvi_min"), max_ndvi=Max("ndvi_max"), avg_veg_pct=Avg("vegetation_area_pct"))
            .order_by("year")
        )
        payload = [
            {
                "year": int(row["year"]),
                "avg_ndvi": fixed(row["avg_ndvi"], 4),
                "min_ndvi": fixed(row["min_ndvi"], 4),
                "max_ndvi": fixed(row["max_ndvi"], 4),
                "avg_veg_pct": fixed(row["avg_veg_pct"], 2),
            }
            for row in rows
        ]
        return ok({"yearly_data": payload})


class TvdiRangeView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id, start, end = _get_range_params(request)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        if _is_gee_source(request):
            try:
                rows = _fetch_gee_records(
                    location_id=location_id,
                    start=start,
                    end=end,
                    data_type="tvdi",
                    province_query=request.query_params.get("province"),
                )
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
        else:
            queryset = TvdiData.objects.filter(location_id=location_id, date__range=[start, end]).order_by("date")
            data = [
                {
                    "date": row.date,
                    "tvdi_mean": to_float(row.tvdi_mean),
                    "tvdi_min": to_float(row.tvdi_min),
                    "tvdi_max": to_float(row.tvdi_max),
                    "lst_mean": to_float(row.lst_mean),
                    "drought_area_pct": to_float(row.drought_area_pct),
                    "drought_class": row.drought_class,
                    "source": row.source,
                }
                for row in queryset
            ]
        avg_tvdi = sum(to_float(r["tvdi_mean"]) for r in data) / len(data) if data else 0
        min_tvdi = min((to_float(r["tvdi_min"]) for r in data), default=0)
        max_tvdi = max((to_float(r["tvdi_max"]) for r in data), default=0)
        avg_lst = sum(to_float(r["lst_mean"]) for r in data) / len(data) if data else 0
        drought_days = len([r for r in data if r["drought_class"] in ("severe", "extreme")])
        drought_pct = (drought_days / len(data) * 100) if data else 0

        return ok(
            {
                "data": data,
                "statistics": {
                    "average": fixed(avg_tvdi, 4),
                    "min": fixed(min_tvdi, 4),
                    "max": fixed(max_tvdi, 4),
                    "avg_lst": fixed(avg_lst, 2),
                    "drought_days": drought_days,
                    "drought_pct": fixed(drought_pct, 2),
                    "classification": tvdi_classification(avg_tvdi),
                    "records": len(data),
                },
            }
        )


class TvdiMonthlyView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id = _parse_int_param(request.query_params.get("location_id"), "location_id", minimum=1)
            year = _parse_int_param(request.query_params.get("year"), "year", minimum=1900, maximum=2100)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        if _is_gee_source(request):
            try:
                rows = _fetch_gee_records(
                    location_id=location_id,
                    start=date(year, 1, 1),
                    end=date(year, 12, 31),
                    data_type="tvdi",
                    province_query=request.query_params.get("province"),
                )
            except ValueError as exc:
                return fail(str(exc), 400, "validation_error")
            except RuntimeError as exc:
                return fail(str(exc), 503, "gee_service_offline")
            except RequestException as exc:
                return fail("Failed to fetch data from GEE service", 502, "gee_service_error", {"message": str(exc)})

            grouped = {}
            for row in rows:
                try:
                    row_date = parse_iso_date(str(row.get("date", ""))[:10], "date")
                except ValueError:
                    continue
                month = row_date.month
                grouped.setdefault(
                    month,
                    {"tvdi_mean": [], "tvdi_min": [], "tvdi_max": [], "lst_mean": [], "drought_area_pct": [], "severe_days": 0},
                )
                grouped[month]["tvdi_mean"].append(to_float(row.get("tvdi_mean")))
                grouped[month]["tvdi_min"].append(to_float(row.get("tvdi_min")))
                grouped[month]["tvdi_max"].append(to_float(row.get("tvdi_max")))
                grouped[month]["lst_mean"].append(to_float(row.get("lst_mean")))
                grouped[month]["drought_area_pct"].append(to_float(row.get("drought_area_pct")))
                if row.get("drought_class") in ("severe", "extreme"):
                    grouped[month]["severe_days"] += 1

            payload = []
            for month, stats in sorted(grouped.items()):
                avg_tvdi = sum(stats["tvdi_mean"]) / len(stats["tvdi_mean"]) if stats["tvdi_mean"] else 0
                payload.append(
                    {
                        "month": month,
                        "avg_tvdi": fixed(avg_tvdi, 4),
                        "min_tvdi": fixed(min(stats["tvdi_min"]) if stats["tvdi_min"] else 0, 4),
                        "max_tvdi": fixed(max(stats["tvdi_max"]) if stats["tvdi_max"] else 0, 4),
                        "avg_lst": fixed(sum(stats["lst_mean"]) / len(stats["lst_mean"]) if stats["lst_mean"] else 0, 2),
                        "avg_drought_pct": fixed(
                            sum(stats["drought_area_pct"]) / len(stats["drought_area_pct"]) if stats["drought_area_pct"] else 0,
                            2,
                        ),
                        "severe_days": int(stats["severe_days"]),
                        "classification": tvdi_classification(to_float(avg_tvdi)),
                    }
                )
        else:
            rows = (
                TvdiData.objects.filter(location_id=location_id, date__year=year)
                .annotate(month=ExtractMonth("date"))
                .values("month")
                .annotate(
                    avg_tvdi=Avg("tvdi_mean"),
                    min_tvdi=Min("tvdi_min"),
                    max_tvdi=Max("tvdi_max"),
                    avg_lst=Avg("lst_mean"),
                    avg_drought_pct=Avg("drought_area_pct"),
                    severe_days=Count("id", filter=Q(drought_class__in=["severe", "extreme"])),
                )
                .order_by("month")
            )
            payload = []
            for row in rows:
                payload.append(
                    {
                        "month": int(row["month"]),
                        "avg_tvdi": fixed(row["avg_tvdi"], 4),
                        "min_tvdi": fixed(row["min_tvdi"], 4),
                        "max_tvdi": fixed(row["max_tvdi"], 4),
                        "avg_lst": fixed(row["avg_lst"], 2),
                        "avg_drought_pct": fixed(row["avg_drought_pct"], 2),
                        "severe_days": int(row["severe_days"]),
                        "classification": tvdi_classification(to_float(row["avg_tvdi"])),
                    }
                )
        return ok({"year": year, "monthly_data": payload})


class TvdiDroughtSummaryView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id = _parse_int_param(request.query_params.get("location_id"), "location_id", minimum=1)
            start_year = _parse_int_param(request.query_params.get("start_year"), "start_year", minimum=1900, maximum=2100)
            end_year = _parse_int_param(request.query_params.get("end_year"), "end_year", minimum=1900, maximum=2100)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")
        if start_year > end_year:
            return fail("Invalid year range: start_year must be <= end_year", 400, "validation_error")

        rows = (
            TvdiData.objects.filter(location_id=location_id, date__year__range=[start_year, end_year])
            .annotate(year=ExtractYear("date"))
            .values("year", "drought_class")
            .annotate(count=Count("id"), avg_tvdi=Avg("tvdi_mean"))
            .order_by("year", "drought_class")
        )
        grouped = {}
        for row in rows:
            year = int(row["year"])
            grouped.setdefault(year, {})
            grouped[year][row["drought_class"]] = {
                "count": int(row["count"]),
                "avg_tvdi": fixed(row["avg_tvdi"], 4),
            }
        return ok({"drought_summary": grouped})


class TvdiSevereEventsView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id = _parse_int_param(request.query_params.get("location_id"), "location_id", minimum=1)
            start = parse_iso_date(request.query_params.get("start"), "start")
            end = parse_iso_date(request.query_params.get("end"), "end")
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")
        if start > end:
            return fail("Invalid date range: start must be before or equal to end", 400, "validation_error")
        rows = (
            TvdiData.objects.filter(
                location_id=location_id,
                date__range=[start, end],
                drought_class__in=["severe", "extreme"],
            )
            .order_by("-tvdi_mean")[:20]
            .values("date", "tvdi_mean", "lst_mean", "drought_area_pct", "drought_class")
        )
        payload = [
            {
                "date": row["date"],
                "tvdi": fixed(row["tvdi_mean"], 4),
                "lst": fixed(row["lst_mean"], 2),
                "drought_pct": fixed(row["drought_area_pct"], 2),
                "classification": row["drought_class"],
            }
            for row in rows
        ]
        return ok({"severe_events": payload})


class DashboardOverviewView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id, start, end = _get_range_params(request)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        rainfall = RainfallData.objects.filter(location_id=location_id, date__range=[start, end]).aggregate(
            avg=Avg("rainfall_mm"), total=Sum("rainfall_mm")
        )
        temperature = TemperatureData.objects.filter(location_id=location_id, date__range=[start, end]).aggregate(
            avg=Avg("temp_mean"), min=Min("temp_min"), max=Max("temp_max")
        )
        soil = SoilMoistureData.objects.filter(location_id=location_id, date__range=[start, end]).aggregate(
            avg_surface=Avg("sm_surface"), avg_root=Avg("sm_rootzone")
        )
        ndvi = NdviData.objects.filter(location_id=location_id, date__range=[start, end]).aggregate(
            avg=Avg("ndvi_mean"),
            min=Min("ndvi_min"),
            max=Max("ndvi_max"),
            veg_pct=Avg("vegetation_area_pct"),
        )
        tvdi = TvdiData.objects.filter(location_id=location_id, date__range=[start, end]).aggregate(
            avg=Avg("tvdi_mean"),
            drought_pct=Avg("drought_area_pct"),
        )
        drought_days = TvdiData.objects.filter(
            location_id=location_id,
            date__range=[start, end],
            drought_class__in=["severe", "extreme"],
        ).count()

        return ok(
            {
                "rainfall": {"total": fixed(rainfall["total"], 2), "average": fixed(rainfall["avg"], 2)},
                "temperature": {
                    "average": fixed(temperature["avg"], 2),
                    "min": fixed(temperature["min"], 2),
                    "max": fixed(temperature["max"], 2),
                },
                "soil_moisture": {"surface": fixed(soil["avg_surface"], 4), "rootzone": fixed(soil["avg_root"], 4)},
                "ndvi": {
                    "average": fixed(ndvi["avg"], 4),
                    "min": fixed(ndvi["min"], 4),
                    "max": fixed(ndvi["max"], 4),
                    "vegetation_pct": fixed(ndvi["veg_pct"], 2),
                },
                "tvdi": {
                    "average": fixed(tvdi["avg"], 4),
                    "drought_area_pct": fixed(tvdi["drought_pct"], 2),
                    "drought_days": drought_days,
                },
            }
        )


class DashboardTimeseriesView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            location_id, start, end = _get_range_params(request)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")
        rows = dashboard_timeseries(location_id, start, end)
        return ok({"timeseries": rows})
