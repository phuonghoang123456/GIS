from __future__ import annotations

import json

from django.db import connection
from django.utils import timezone
from rest_framework.views import APIView
from shapely.geometry import GeometryCollection, mapping, shape
from shapely.ops import unary_union

from apps.common.responses import fail, ok

from .models import AnalysisAreaHistory


ANALYSIS_AREA_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS analysis_area_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    province_name VARCHAR(255),
    source_type VARCHAR(50) NOT NULL,
    boundary_code VARCHAR(50),
    location_id BIGINT REFERENCES locations(id),
    geometry JSONB NOT NULL,
    centroid_lat DOUBLE PRECISION,
    centroid_lng DOUBLE PRECISION,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_area_history_user_last_used
    ON analysis_area_history(user_id, last_used_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_area_history_location_id
    ON analysis_area_history(location_id);
"""


def ensure_analysis_area_history_table():
    with connection.cursor() as cursor:
        cursor.execute(ANALYSIS_AREA_HISTORY_SQL)


def normalize_geometry_payload(geometry_payload):
    if not isinstance(geometry_payload, dict):
        raise ValueError("Geometry payload must be a JSON object.")

    geometry_type = geometry_payload.get("type")
    if geometry_type == "Feature":
        geometry = geometry_payload.get("geometry")
        if not geometry:
            raise ValueError("GeoJSON Feature must include geometry.")
        return geometry_payload

    if geometry_type == "FeatureCollection":
        features = geometry_payload.get("features") or []
        if not features:
            raise ValueError("GeoJSON FeatureCollection must include at least one feature.")
        return geometry_payload

    if geometry_type and geometry_payload.get("coordinates") is not None:
        return {
            "type": "Feature",
            "properties": {},
            "geometry": geometry_payload,
        }

    raise ValueError("Unsupported geometry payload. Use GeoJSON Feature, FeatureCollection, Polygon or MultiPolygon.")


def _iter_shapes(geometry_payload):
    normalized = normalize_geometry_payload(geometry_payload)
    if normalized["type"] == "FeatureCollection":
        for feature in normalized.get("features", []):
            geometry = feature.get("geometry")
            if geometry:
                yield shape(geometry)
        return

    if normalized["type"] == "Feature":
        yield shape(normalized["geometry"])
        return

    yield shape(normalized)


def compute_geometry_center(geometry_payload):
    geometries = [item for item in _iter_shapes(geometry_payload) if not item.is_empty]
    if not geometries:
        return None, None

    merged = unary_union(geometries)
    if isinstance(merged, GeometryCollection) and not merged.geoms:
        return None, None

    point = merged.representative_point() if hasattr(merged, "representative_point") else merged.centroid
    return float(point.y), float(point.x)


def serialize_history_row(row: AnalysisAreaHistory):
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "province_name": row.province_name,
        "source_type": row.source_type,
        "boundary_code": row.boundary_code,
        "location_id": row.location_id,
        "geometry": row.geometry,
        "centroid_lat": row.centroid_lat,
        "centroid_lng": row.centroid_lng,
        "metadata": row.metadata or {},
        "created_at": row.created_at,
        "last_used_at": row.last_used_at,
    }


def record_analysis_area_usage(user, payload: dict, *, location_id=None, extra_metadata: dict | None = None):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    ensure_analysis_area_history_table()
    geometry = normalize_geometry_payload(payload.get("geometry"))
    centroid_lat, centroid_lng = compute_geometry_center(geometry)
    metadata = dict(payload.get("metadata") or {})
    if extra_metadata:
        metadata.update(extra_metadata)

    history = AnalysisAreaHistory.objects.create(
        user_id=user.id,
        name=payload.get("area_name") or payload.get("name") or "Vùng phân tích tùy chọn",
        province_name=payload.get("province") or payload.get("province_name") or "",
        source_type=payload.get("source_type") or "geometry",
        boundary_code=payload.get("boundary_code") or None,
        location_id=location_id or payload.get("location_id") or None,
        geometry=geometry,
        centroid_lat=centroid_lat,
        centroid_lng=centroid_lng,
        metadata=metadata,
        created_at=timezone.now(),
        last_used_at=timezone.now(),
    )
    return history


def update_analysis_area_location(history_id: int | None, user_id: int | None, location_id: int | None):
    if not history_id or not user_id or not location_id:
        return
    ensure_analysis_area_history_table()
    AnalysisAreaHistory.objects.filter(id=history_id, user_id=user_id).update(
        location_id=location_id,
        last_used_at=timezone.now(),
    )


class AnalysisAreaHistoryView(APIView):
    def get(self, request):
        ensure_analysis_area_history_table()
        try:
            limit = int(request.query_params.get("limit", 12))
        except (TypeError, ValueError):
            return fail("Invalid limit. Must be an integer.", 400, "validation_error")
        limit = max(1, min(limit, 50))
        rows = AnalysisAreaHistory.objects.filter(user_id=request.user.id).order_by("-last_used_at")[:limit]
        return ok([serialize_history_row(row) for row in rows])

    def post(self, request):
        try:
            history = record_analysis_area_usage(
                request.user,
                request.data,
                extra_metadata={"saved_from": "manual_history_save"},
            )
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        return ok(serialize_history_row(history), 201)
