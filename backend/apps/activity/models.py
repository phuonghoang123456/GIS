from django.db import models
from django.utils import timezone


class ActivityLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey("accounts.User", on_delete=models.DO_NOTHING, db_column="user_id")
    activity_type = models.CharField(max_length=100)
    page = models.CharField(max_length=100)
    details = models.JSONField(default=dict, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "user_activity_logs"
        managed = False

    @classmethod
    def create(cls, user_id, activity_type, page, details, ip_address, user_agent):
        return cls.objects.create(
            user_id=user_id,
            activity_type=activity_type,
            page=page,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=timezone.now(),
        )
