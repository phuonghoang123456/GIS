from datetime import datetime, timedelta

from django.db.models import Count, Max, Min
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.responses import fail, ok

from .models import ActivityLog
from .serializers import LogActivitySerializer


def _parse_non_negative_int(value, name: str, default: int, max_value: int | None = None) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {name}. Must be an integer.") from exc

    if parsed < 0:
        raise ValueError(f"Invalid {name}. Must be >= 0.")
    if max_value is not None and parsed > max_value:
        raise ValueError(f"Invalid {name}. Must be <= {max_value}.")
    return parsed


def _parse_iso_datetime(value: str, name: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {name}. Use ISO-8601 format.") from exc


class LogActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogActivitySerializer(data=request.data)
        if not serializer.is_valid():
            return fail("Invalid payload", 400, "validation_error", serializer.errors)

        payload = serializer.validated_data
        log = ActivityLog.create(
            user_id=request.user.id,
            activity_type=payload["activityType"],
            page=payload["page"],
            details=payload.get("details", {}),
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.headers.get("User-Agent"),
        )
        return ok({"message": "Activity logged", "log": {"id": log.id}}, 201)


class ActivityHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            limit = _parse_non_negative_int(request.query_params.get("limit"), "limit", default=50, max_value=500)
            offset = _parse_non_negative_int(request.query_params.get("offset"), "offset", default=0)
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")
        logs = (
            ActivityLog.objects.filter(user_id=request.user.id)
            .order_by("-created_at")[offset : offset + limit]
            .values("id", "activity_type", "page", "details", "created_at")
        )
        return ok({"activities": list(logs)})


class ActivityStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_raw = request.query_params.get("startDate")
        end_raw = request.query_params.get("endDate")

        try:
            if start_raw:
                start = _parse_iso_datetime(start_raw, "startDate")
            else:
                start = timezone.now() - timedelta(days=30)

            if end_raw:
                end = _parse_iso_datetime(end_raw, "endDate")
            else:
                end = timezone.now()
        except ValueError as exc:
            return fail(str(exc), 400, "validation_error")

        if start > end:
            return fail("Invalid date range: startDate must be before endDate.", 400, "validation_error")

        queryset = ActivityLog.objects.filter(
            user_id=request.user.id,
            created_at__gte=start,
            created_at__lte=end,
        )

        stats = list(
            queryset.values("activity_type")
            .annotate(
                count=Count("id"),
                first_activity=Min("created_at"),
                last_activity=Max("created_at"),
            )
            .order_by("-count")
        )
        recent = list(
            queryset.order_by("-created_at")
            .values("activity_type", "page", "details", "created_at")[:10]
        )

        return ok({"stats": stats, "recentActivities": recent, "period": {"start": start, "end": end}})
