from rest_framework import serializers


class LogActivitySerializer(serializers.Serializer):
    activityType = serializers.CharField(max_length=100)
    page = serializers.CharField(max_length=100)
    details = serializers.JSONField(required=False)
