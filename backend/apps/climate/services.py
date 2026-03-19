from __future__ import annotations

from datetime import date, datetime

from django.db import connection

from apps.common.helpers import classify_ndvi, classify_tvdi


def parse_iso_date(value: str | None, field_name: str) -> date:
    if not value:
        raise ValueError(f"Missing required parameter: {field_name}")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid date format for {field_name}. Use YYYY-MM-DD") from exc


def ndvi_classification(value: float | None):
    return classify_ndvi(value)


def tvdi_classification(value: float | None):
    return classify_tvdi(value)


def dashboard_timeseries(location_id: int, start: str, end: str):
    query = """
      SELECT
        COALESCE(r.date, t.date, s.date, n.date, tv.date) as date,
        r.rainfall_mm,
        t.temp_mean, t.temp_min, t.temp_max,
        s.sm_surface, s.sm_rootzone,
        n.ndvi_mean,
        tv.tvdi_mean, tv.drought_class
      FROM rainfall_data r
      FULL OUTER JOIN temperature_data t
        ON r.location_id = t.location_id AND r.date = t.date
      FULL OUTER JOIN soil_moisture_data s
        ON COALESCE(r.location_id, t.location_id) = s.location_id
        AND COALESCE(r.date, t.date) = s.date
      FULL OUTER JOIN ndvi_data n
        ON COALESCE(r.location_id, t.location_id, s.location_id) = n.location_id
        AND COALESCE(r.date, t.date, s.date) = n.date
      FULL OUTER JOIN tvdi_data tv
        ON COALESCE(r.location_id, t.location_id, s.location_id, n.location_id) = tv.location_id
        AND COALESCE(r.date, t.date, s.date, n.date) = tv.date
      WHERE COALESCE(r.location_id, t.location_id, s.location_id, n.location_id, tv.location_id) = %s
        AND COALESCE(r.date, t.date, s.date, n.date, tv.date) BETWEEN %s AND %s
      ORDER BY date
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [location_id, start, end])
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return rows
